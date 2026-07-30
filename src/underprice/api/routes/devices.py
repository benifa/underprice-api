from __future__ import annotations

from fastapi import APIRouter

from underprice.api.deps import get_container
from underprice.api.schemas import DeviceRequest

router = APIRouter(tags=["devices"])


@router.post("/v1/devices", status_code=204)
def register_device(body: DeviceRequest) -> None:
    get_container().store.register_device(body.install_id, body.fcm_token)
