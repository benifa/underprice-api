"""Store protocol — Memory and Postgres share the same agent/API surface."""

from __future__ import annotations

from typing import Protocol

from underprice.models import Deal, Prefs, ScoreJob, ScoreResult


class Store(Protocol):
    def save_job(self, job: ScoreJob) -> ScoreJob: ...

    def get_job(self, job_id: str) -> ScoreJob | None: ...

    def save_deal_from_score(
        self,
        title: str,
        description: str,
        url: str | None,
        result: ScoreResult,
    ) -> Deal | None: ...

    def list_deals(self, *, cursor: int = 0, limit: int = 20) -> tuple[list[Deal], int | None]: ...

    def get_deal(self, deal_id: str) -> Deal | None: ...

    def save_prefs(self, prefs: Prefs) -> Prefs: ...

    def get_prefs(self, install_id: str) -> Prefs | None: ...

    def register_device(self, install_id: str, fcm_token: str) -> None: ...

    def record_price_sample(self, category: str, price: float) -> None: ...

    def known_urls(self) -> list[str]: ...

    def category_median(self, category: str, *, min_samples: int = 5) -> float | None: ...
