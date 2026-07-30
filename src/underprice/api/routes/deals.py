from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from underprice.api.deps import get_container
from underprice.api.schemas import DealListResponse, DealResponse

router = APIRouter(tags=["deals"])


@router.get("/v1/deals", response_model=DealListResponse)
def list_deals(
    cursor: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> DealListResponse:
    """Precomputed feed only — never scores on read."""
    items, next_cursor = get_container().store.list_deals(cursor=cursor, limit=limit)
    return DealListResponse(
        items=[DealResponse.model_validate(d.model_dump()) for d in items],
        next_cursor=next_cursor,
    )


@router.get("/v1/deals/{deal_id}", response_model=DealResponse)
def get_deal(deal_id: str, explain: int = Query(0, ge=0, le=1)) -> DealResponse:
    deal = get_container().store.get_deal(deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="deal not found")
    # explain=1 may trigger Judge in Phase 5; Phase 1 returns stored signals.
    _ = explain
    return DealResponse.model_validate(deal.model_dump())
