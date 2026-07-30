"""CategoryMedian — cheap CPU gate before RAG / GPU.

Uses DB/store sample medians when enough observations exist; otherwise static priors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from underprice.config import Settings
from underprice.logging_setup import agent_logger
from underprice.models import Candidate, Signal

if TYPE_CHECKING:
    from underprice.store.base import Store

log = agent_logger("CategoryMedian")

# Bootstrap priors until price_samples has enough rows per category.
CATEGORY_PRIORS: dict[str, float] = {
    "electronics": 180.0,
    "headphones": 90.0,
    "laptop": 650.0,
    "phone": 400.0,
    "home": 75.0,
    "toys": 35.0,
    "apparel": 40.0,
}


class CategoryMedianSpecialist:
    name = "median"

    def __init__(self, settings: Settings, store: Store | None = None) -> None:
        self._default = settings.default_category_median
        self._min_samples = settings.median_min_samples
        self._store = store

    def estimate(self, candidate: Candidate) -> Signal:
        category = (candidate.category or infer_category(candidate)).lower()
        source = "prior"
        value: float | None = None

        if self._store is not None:
            observed = self._store.category_median(category, min_samples=self._min_samples)
            if observed is not None:
                value = observed
                source = "store"

        if value is None:
            value = CATEGORY_PRIORS.get(category, self._default)

        log.info("median=%.2f category=%s source=%s", value, category, source)
        return Signal(
            source=self.name,
            value=value,
            notes=f"category={category} source={source}",
            meta={"category": category, "source": source, "min_samples": self._min_samples},
        )


def infer_category(candidate: Candidate) -> str:
    text = candidate.text_for_pricing().lower()
    for key in CATEGORY_PRIORS:
        if key in text:
            return key
    return "general"
