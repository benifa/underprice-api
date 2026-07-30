from __future__ import annotations

from underprice.agents.ensemble import EnsembleAgent
from underprice.cache.estimate_cache import EstimateCache
from underprice.config import Settings
from underprice.models import Candidate, Signal
from underprice.specialists.fine_tuned import FineTunedListPriceSpecialist
from underprice.specialists.median import CategoryMedianSpecialist
from underprice.specialists.rag import RagCompsSpecialist


class FixedMedian(CategoryMedianSpecialist):
    def __init__(self, value: float) -> None:
        self._value = value
        self.name = "median"

    def estimate(self, candidate: Candidate) -> Signal:
        return Signal(source="median", value=self._value)


class FixedFT(FineTunedListPriceSpecialist):
    def __init__(self, value: float, settings: Settings) -> None:
        super().__init__(settings)
        self._value = value

    def estimate(self, candidate: Candidate) -> Signal:
        return Signal(
            source="fine_tuned",
            value=self._value,
            meta={"revision": self.settings.adapter_revision},
        )


def test_median_gate_skips_gpu(settings: Settings) -> None:
    # ask 100 / median 80 = 1.25 > 0.95 → early exit, no fine_tuned
    agent = EnsembleAgent(
        settings,
        EstimateCache(),
        median=FixedMedian(80.0),
        fine_tuned=FixedFT(50.0, settings),
    )
    result = agent.score(Candidate(title="Overpriced gadget", ask=100.0))
    assert result.early_exit_reason == "median_gate"
    assert "fine_tuned" not in result.stages_run
    assert result.fair_value == 80.0
    assert result.confidence.value == "low"


def test_cascade_runs_fine_tuned_when_under_median(settings: Settings) -> None:
    # ask 50 / median 100 = 0.5 <= 0.95 → continue to FT
    agent = EnsembleAgent(
        settings,
        EstimateCache(),
        median=FixedMedian(100.0),
        fine_tuned=FixedFT(90.0, settings),
    )
    result = agent.score(Candidate(title="Headphones", ask=50.0, category="headphones"))
    assert result.early_exit_reason is None
    assert result.stages_run == ["median", "rag", "fine_tuned"]
    assert result.fair_value == 90.0
    assert result.deal_score == round(50 / 90, 4)
    assert result.messenger_eligible is True
    assert result.confidence.value == "high"
    assert result.model_revision == settings.adapter_revision


def test_cache_hit_skips_specialists(settings: Settings) -> None:
    cache = EstimateCache()
    agent = EnsembleAgent(
        settings,
        cache,
        median=FixedMedian(100.0),
        fine_tuned=FixedFT(80.0, settings),
    )
    c = Candidate(title="Cached item", ask=40.0)
    first = agent.score(c)
    second = agent.score(Candidate(title="Cached item", ask=40.0))
    assert first.cached is False
    assert second.cached is True
    assert second.fair_value == first.fair_value


def test_gray_zone_records_judge_stage(settings: Settings) -> None:
    # deal_score = 80/100 = 0.8 → gray zone
    agent = EnsembleAgent(
        settings,
        EstimateCache(),
        median=FixedMedian(200.0),
        fine_tuned=FixedFT(100.0, settings),
        rag=RagCompsSpecialist(),
    )
    result = agent.score(Candidate(title="Gray zone deal", ask=80.0))
    assert result.deal_score == 0.8
    assert "judge" in result.stages_run
