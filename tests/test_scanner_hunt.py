from __future__ import annotations

from underprice.agents.planner import PlannerAgent
from underprice.agents.scanner import ScannerAgent
from underprice.config import Settings
from underprice.ingest.rss import ScrapedDeal, extract_ask_price
from underprice.models import Candidate, ScoreResult, Signal
from underprice.store.memory import MemoryStore


def test_extract_ask_price_prefers_absolute() -> None:
    assert extract_ask_price("Sony WH-1000XM5 for $198 shipped") == 198.0
    assert extract_ask_price("Save $50 on item now $149") == 149.0
    assert extract_ask_price("$100 off headphones — no clear ask") is None


class FakeScraper:
    def fetch(self, exclude_urls=None):  # noqa: ANN001
        return [
            ScrapedDeal(
                title="Sony headphones for $60",
                summary="Noise cancelling for $60",
                url="https://www.dealnews.com/products/sony/1.html",
                details="Sony WH over-ear ANC headphones. Price $60.",
                features="Bluetooth",
                category="electronics",
                feed_url="https://www.dealnews.com/c142/Electronics/?rss=1",
            ),
            ScrapedDeal(
                title="$100 off mystery gadget",
                summary="Save big",
                url="https://www.dealnews.com/products/x/2.html",
                details="Discount only, no clear ask.",
                features="",
                category="electronics",
                feed_url="https://www.dealnews.com/c142/Electronics/?rss=1",
            ),
        ]


def test_scanner_heuristic_builds_candidates(settings: Settings) -> None:
    settings = settings.model_copy(update={"use_scanner_llm": False, "openai_api_key": ""})
    agent = ScannerAgent(settings, scraper=FakeScraper())  # type: ignore[arg-type]
    candidates = agent.scan()
    assert len(candidates) == 1
    assert candidates[0].ask == 60.0
    assert candidates[0].source == "dealnews"
    assert "dealnews.com" in (candidates[0].url or "")


def test_planner_hunt_persists_hot_deals(settings: Settings) -> None:
    settings = settings.model_copy(update={"use_scanner_llm": False, "openai_api_key": ""})
    store = MemoryStore()

    class FixedEnsemble:
        def score(self, candidate: Candidate) -> ScoreResult:
            return ScoreResult(
                candidate_id=candidate.id,
                ask=candidate.ask,
                fair_value=200.0,
                deal_score=candidate.ask / 200.0,
                messenger_eligible=True,
                stages_run=["median", "fine_tuned"],
                signals={"fine_tuned": Signal(source="fine_tuned", value=200.0)},
            )

    class NotifyMessenger:
        def __init__(self) -> None:
            self.calls = 0

        def notify(self, candidate, result):  # noqa: ANN001
            self.calls += 1
            return True

    messenger = NotifyMessenger()
    planner = PlannerAgent(
        ScannerAgent(settings, scraper=FakeScraper()),  # type: ignore[arg-type]
        FixedEnsemble(),  # type: ignore[arg-type]
        messenger,  # type: ignore[arg-type]
        store=store,
    )
    results = planner.hunt_tick()
    assert len(results) == 1
    assert len(store.deals) == 1
    assert store.deals[0].url and "dealnews.com" in store.deals[0].url
    assert messenger.calls == 1
