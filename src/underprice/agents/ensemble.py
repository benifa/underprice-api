"""Ensemble — sole specialist orchestrator. Cascade is an ops policy, not a design collapse."""

from __future__ import annotations

from typing import TYPE_CHECKING

from underprice.agents.base import Agent
from underprice.cache.estimate_cache import EstimateCache, content_hash
from underprice.config import Settings
from underprice.models import Candidate, ScoreResult, Signal
from underprice.specialists.fine_tuned import FineTunedListPriceSpecialist
from underprice.specialists.judge import LlmJudgeSpecialist
from underprice.specialists.median import CategoryMedianSpecialist, infer_category
from underprice.specialists.rag import RagCompsSpecialist

if TYPE_CHECKING:
    from underprice.store.base import Store


class EnsembleAgent(Agent):
    name = "Ensemble"

    def __init__(
        self,
        settings: Settings,
        cache: EstimateCache | None = None,
        store: Store | None = None,
        *,
        median: CategoryMedianSpecialist | None = None,
        rag: RagCompsSpecialist | None = None,
        fine_tuned: FineTunedListPriceSpecialist | None = None,
        judge: LlmJudgeSpecialist | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.store = store
        self.cache = cache or EstimateCache(settings.cache_ttl_days)
        self.median = median or CategoryMedianSpecialist(settings, store=store)
        self.rag = rag or RagCompsSpecialist()
        self.fine_tuned = fine_tuned or FineTunedListPriceSpecialist(settings)
        self.judge = judge or LlmJudgeSpecialist()

    def score(self, candidate: Candidate) -> ScoreResult:
        key = content_hash(candidate)
        hit = self.cache.get(key)
        if hit is not None:
            self.log.info("cache hit hash=%s", key[:12])
            return hit.model_copy(update={"candidate_id": candidate.id})

        signals: dict[str, Signal] = {}
        stages: list[str] = []
        early: str | None = None

        # Stage 1 — median gate
        stages.append("median")
        signals["median"] = self.median.estimate(candidate)
        median_val = signals["median"].value
        if median_val and median_val > 0:
            ratio = candidate.ask / median_val
            if ratio > self.settings.median_gate:
                early = "median_gate"
                self.log.info("early exit median_gate ask/median=%.3f", ratio)
                result = self._fuse(candidate, signals, stages, early, key)
                self.cache.put(key, result)
                self._record_sample(candidate, result)
                return result

        # Stage 2 — RAG (stub may return None; still recorded)
        stages.append("rag")
        signals["rag"] = self.rag.estimate(candidate)
        rag_val = signals["rag"].value
        interesting = True
        if rag_val and rag_val > 0:
            interesting = (candidate.ask / rag_val) <= self.settings.median_gate
        # Phase 1: RAG stub → always continue to GPU when median gate passed.
        if rag_val is None:
            interesting = True
        if not interesting:
            early = "rag_gate"
            result = self._fuse(candidate, signals, stages, early, key)
            self.cache.put(key, result)
            self._record_sample(candidate, result)
            return result

        # Stage 3 — FineTuned GPU (or local heuristic in dev)
        stages.append("fine_tuned")
        signals["fine_tuned"] = self.fine_tuned.estimate(candidate)

        result = self._fuse(candidate, signals, stages, early, key)

        # Stage 4 — Judge only in gray zone (Phase 5 stub still records stage when gray)
        if result.deal_score is not None:
            low, high = self.settings.gray_zone_low, self.settings.gray_zone_high
            if low <= result.deal_score <= high:
                stages.append("judge")
                signals["judge"] = self.judge.estimate(candidate)
                result = self._fuse(candidate, signals, stages, early, key)

        self.cache.put(key, result)
        self._record_sample(candidate, result)
        self.log.info(
            "scored deal_score=%s confidence=%s stages=%s",
            result.deal_score,
            result.confidence,
            stages,
        )
        return result

    def _record_sample(self, candidate: Candidate, result: ScoreResult) -> None:
        if self.store is None:
            return
        category = candidate.category or infer_category(candidate)
        # Prefer fused fair value (list-price estimate); fall back to ask.
        price = result.fair_value if result.fair_value and result.fair_value > 0 else candidate.ask
        self.store.record_price_sample(category, price)

    def _fuse(
        self,
        candidate: Candidate,
        signals: dict[str, Signal],
        stages: list[str],
        early: str | None,
        key: str,
    ) -> ScoreResult:
        return ScoreResult.fuse(
            candidate=candidate,
            signals=signals,
            stages_run=list(stages),
            early_exit_reason=early,
            hot_deal=self.settings.hot_deal,
            model_revision=self.settings.adapter_revision,
            content_hash=key,
        )
