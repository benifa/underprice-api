from __future__ import annotations

from fastapi import APIRouter

from underprice.api.deps import get_container
from underprice.api.schemas import HuntResponse

router = APIRouter(tags=["hunt"])


@router.post("/v1/hunt", response_model=HuntResponse)
def run_hunt() -> HuntResponse:
    """Trigger one hunt tick: DealNews RSS → Ensemble → persist hot deals."""
    c = get_container()
    assert c.planner is not None
    results = c.planner.hunt_tick()
    hot = sum(1 for r in results if r.messenger_eligible)
    return HuntResponse(scanned=len(results), hot=hot, results=results)
