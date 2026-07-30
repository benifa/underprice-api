"""In-memory store — default for tests and local when DATABASE_URL is unset."""

from __future__ import annotations

import statistics

from underprice.models import Deal, Prefs, ScoreJob, ScoreResult


class MemoryStore:
    def __init__(self) -> None:
        self.deals: list[Deal] = []
        self.jobs: dict[str, ScoreJob] = {}
        self.prefs: dict[str, Prefs] = {}
        self.devices: dict[str, str] = {}  # install_id -> fcm_token
        self.price_samples: dict[str, list[float]] = {}

    def save_job(self, job: ScoreJob) -> ScoreJob:
        self.jobs[job.job_id] = job
        return job

    def get_job(self, job_id: str) -> ScoreJob | None:
        return self.jobs.get(job_id)

    def save_deal_from_score(
        self,
        title: str,
        description: str,
        url: str | None,
        result: ScoreResult,
    ) -> Deal | None:
        if result.fair_value is None or result.deal_score is None:
            return None
        if not result.messenger_eligible:
            return None
        deal = Deal(
            id=result.candidate_id,
            title=title,
            description=description,
            ask=result.ask,
            url=url,
            fair_value=result.fair_value,
            deal_score=result.deal_score,
            confidence=result.confidence,
            signals=result.signals,
            stages_run=result.stages_run,
        )
        self.deals.insert(0, deal)
        return deal

    def list_deals(self, *, cursor: int = 0, limit: int = 20) -> tuple[list[Deal], int | None]:
        page = self.deals[cursor : cursor + limit]
        next_cursor = cursor + limit if cursor + limit < len(self.deals) else None
        return page, next_cursor

    def get_deal(self, deal_id: str) -> Deal | None:
        for deal in self.deals:
            if deal.id == deal_id:
                return deal
        return None

    def save_prefs(self, prefs: Prefs) -> Prefs:
        self.prefs[prefs.install_id] = prefs
        return prefs

    def get_prefs(self, install_id: str) -> Prefs | None:
        return self.prefs.get(install_id)

    def register_device(self, install_id: str, fcm_token: str) -> None:
        self.devices[install_id] = fcm_token

    def record_price_sample(self, category: str, price: float) -> None:
        if price <= 0:
            return
        key = category.lower().strip() or "general"
        self.price_samples.setdefault(key, []).append(float(price))

    def category_median(self, category: str, *, min_samples: int = 5) -> float | None:
        key = category.lower().strip() or "general"
        samples = self.price_samples.get(key, [])
        if len(samples) < min_samples:
            return None
        return float(statistics.median(samples))

    def known_urls(self) -> list[str]:
        return [d.url for d in self.deals if d.url]
