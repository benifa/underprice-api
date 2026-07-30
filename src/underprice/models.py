"""Domain types shared by agents, specialists, and the HTTP API."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class CandidateStatus(StrEnum):
    PENDING = "pending"
    SCORED = "scored"
    REJECTED = "rejected"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Candidate(BaseModel):
    """Normalized listing input (paste path or scanner ingest)."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str = ""
    ask: float
    url: str | None = None
    source: str = "paste"
    category: str | None = None
    status: CandidateStatus = CandidateStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("ask")
    @classmethod
    def ask_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("ask must be > 0")
        return v

    def text_for_pricing(self) -> str:
        parts = [self.title.strip()]
        if self.description.strip():
            parts.append(self.description.strip())
        return "\n".join(parts)


class Signal(BaseModel):
    """Output contract for every specialist."""

    source: str
    value: float | None = None
    notes: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class ScoreResult(BaseModel):
    """Fused estimate written to deals / returned on /v1/score."""

    candidate_id: str
    ask: float
    fair_value: float | None
    deal_score: float | None = None  # ask / fair_value; lower is better
    confidence: Confidence = Confidence.LOW
    signals: dict[str, Signal] = Field(default_factory=dict)
    stages_run: list[str] = Field(default_factory=list)
    early_exit_reason: str | None = None
    messenger_eligible: bool = False
    cached: bool = False
    model_revision: str | None = None
    content_hash: str | None = None

    @classmethod
    def fuse(
        cls,
        *,
        candidate: Candidate,
        signals: dict[str, Signal],
        stages_run: list[str],
        early_exit_reason: str | None,
        hot_deal: float,
        model_revision: str | None,
        cached: bool = False,
        content_hash: str | None = None,
    ) -> ScoreResult:
        fair = _prefer_fair_value(signals)
        deal_score = (candidate.ask / fair) if fair and fair > 0 else None
        confidence = _confidence(stages_run, signals)
        eligible = deal_score is not None and deal_score <= hot_deal
        return cls(
            candidate_id=candidate.id,
            ask=candidate.ask,
            fair_value=fair,
            deal_score=round(deal_score, 4) if deal_score is not None else None,
            confidence=confidence,
            signals=signals,
            stages_run=stages_run,
            early_exit_reason=early_exit_reason,
            messenger_eligible=eligible,
            cached=cached,
            model_revision=model_revision,
            content_hash=content_hash,
        )


def _prefer_fair_value(signals: dict[str, Signal]) -> float | None:
    for key in ("fine_tuned", "rag", "median"):
        sig = signals.get(key)
        if sig and sig.value is not None and sig.value > 0:
            return float(sig.value)
    return None


def _confidence(stages_run: list[str], signals: dict[str, Signal]) -> Confidence:
    ft = signals.get("fine_tuned")
    rag = signals.get("rag")
    if "fine_tuned" in stages_run and ft and ft.value is not None:
        if rag and rag.value is not None and ft.value > 0:
            ratio = rag.value / ft.value
            if 0.85 <= ratio <= 1.15:
                return Confidence.HIGH
        return Confidence.HIGH
    if "rag" in stages_run and rag and rag.value is not None:
        return Confidence.MEDIUM
    return Confidence.LOW


class ScoreJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    status: JobStatus = JobStatus.QUEUED
    stages: list[str] = Field(default_factory=list)
    result: ScoreResult | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Deal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str = ""
    ask: float
    url: str | None = None
    fair_value: float
    deal_score: float
    confidence: Confidence
    signals: dict[str, Signal] = Field(default_factory=dict)
    stages_run: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DeviceRegistration(BaseModel):
    install_id: str
    fcm_token: str


class Prefs(BaseModel):
    install_id: str
    keywords: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    min_score: float = 0.7
    notify_enabled: bool = True
