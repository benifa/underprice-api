from __future__ import annotations

from fastapi import APIRouter

from underprice.api.deps import get_container
from underprice.api.schemas import PrefsRequest, PrefsResponse
from underprice.models import Prefs

router = APIRouter(tags=["prefs"])


@router.put("/v1/prefs", response_model=PrefsResponse)
def put_prefs(body: PrefsRequest) -> PrefsResponse:
    prefs = Prefs.model_validate(body.model_dump())
    saved = get_container().store.save_prefs(prefs)
    return PrefsResponse.model_validate(saved.model_dump())
