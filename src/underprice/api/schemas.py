"""HTTP request/response DTOs (keep domain models out of OpenAPI where useful)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from underprice.models import Confidence, JobStatus, ScoreResult, Signal


class ScoreRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = ""
    ask: float = Field(gt=0, le=9999)
    url: str | None = None
    category: str | None = None


class ScoreResponse(BaseModel):
    job_id: str | None = None
    status: JobStatus = JobStatus.DONE
    result: ScoreResult | None = None


class DealResponse(BaseModel):
    id: str
    title: str
    description: str
    ask: float
    url: str | None
    fair_value: float
    deal_score: float
    confidence: Confidence
    signals: dict[str, Signal]
    stages_run: list[str]


class DealListResponse(BaseModel):
    items: list[DealResponse]
    next_cursor: int | None = None


class DeviceRequest(BaseModel):
    install_id: str
    fcm_token: str


class PrefsRequest(BaseModel):
    install_id: str
    keywords: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    min_score: float = 0.7
    notify_enabled: bool = True


class PrefsResponse(PrefsRequest):
    pass


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str


class HuntResponse(BaseModel):
    scanned: int
    hot: int
    results: list[ScoreResult] = Field(default_factory=list)
