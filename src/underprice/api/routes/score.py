from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from underprice.api.deps import get_container
from underprice.api.schemas import ScoreRequest, ScoreResponse
from underprice.models import Candidate, JobStatus, ScoreJob

router = APIRouter(tags=["score"])


@router.post("/v1/score", response_model=ScoreResponse)
def score_listing(body: ScoreRequest) -> ScoreResponse:
    """Paste / share path. Phase 1 runs Ensemble inline (200). GPU cold → 202 later."""
    c = get_container()
    candidate = Candidate(
        title=body.title,
        description=body.description,
        ask=body.ask,
        url=body.url,
        category=body.category,
        source="paste",
    )
    job = ScoreJob(status=JobStatus.RUNNING, stages=["ensemble"])
    c.store.save_job(job)

    try:
        assert c.planner is not None
        result = c.planner.score_on_demand(candidate)
        job.status = JobStatus.DONE
        job.stages = list(result.stages_run)
        job.result = result
        job.updated_at = datetime.now(UTC)
        c.store.save_job(job)
        c.store.save_deal_from_score(body.title, body.description, body.url, result)
        return ScoreResponse(job_id=job.job_id, status=job.status, result=result)
    except Exception as exc:  # noqa: BLE001 — surface as failed job
        job.status = JobStatus.FAILED
        job.error = str(exc)
        job.updated_at = datetime.now(UTC)
        c.store.save_job(job)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/v1/score/{job_id}", response_model=ScoreResponse)
def get_score_job(job_id: str) -> ScoreResponse:
    job = get_container().store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return ScoreResponse(job_id=job.job_id, status=job.status, result=job.result)
