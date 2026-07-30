from __future__ import annotations

from underprice.agents.ensemble import EnsembleAgent
from underprice.cache.estimate_cache import EstimateCache
from underprice.config import Settings
from underprice.models import Candidate
from underprice.specialists.fine_tuned import FineTunedListPriceSpecialist
from underprice.specialists.median import CategoryMedianSpecialist
from underprice.store.memory import MemoryStore


def test_median_uses_store_when_enough_samples(settings: Settings) -> None:
    store = MemoryStore()
    for price in (80.0, 90.0, 100.0, 110.0, 120.0):
        store.record_price_sample("headphones", price)

    specialist = CategoryMedianSpecialist(settings, store=store)
    signal = specialist.estimate(
        Candidate(title="Sony headphones", ask=50.0, category="headphones")
    )
    assert signal.value == 100.0
    assert signal.meta["source"] == "store"


def test_median_falls_back_to_prior_with_few_samples(settings: Settings) -> None:
    store = MemoryStore()
    store.record_price_sample("headphones", 999.0)
    specialist = CategoryMedianSpecialist(settings, store=store)
    signal = specialist.estimate(
        Candidate(title="Sony headphones", ask=50.0, category="headphones")
    )
    assert signal.meta["source"] == "prior"
    assert signal.value == 90.0  # CATEGORY_PRIORS headphones


def test_ensemble_records_price_samples(settings: Settings) -> None:
    store = MemoryStore()

    class FixedFT(FineTunedListPriceSpecialist):
        def estimate(self, candidate: Candidate):
            from underprice.models import Signal

            return Signal(source="fine_tuned", value=200.0)

    agent = EnsembleAgent(
        settings,
        EstimateCache(),
        store=store,
        median=CategoryMedianSpecialist(settings, store=store),
        fine_tuned=FixedFT(settings),
    )
    # ask 40 / prior 90 → passes median gate
    agent.score(Candidate(title="Deal phones", ask=40.0, category="phone"))
    assert len(store.price_samples["phone"]) == 1
    assert store.price_samples["phone"][0] == 200.0
