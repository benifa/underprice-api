"""Estimate cache — in-process + optional Modal Dict (shared across workers)."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Protocol

from underprice.logging_setup import agent_logger
from underprice.models import Candidate, ScoreResult

log = agent_logger("EstimateCache")


def content_hash(candidate: Candidate) -> str:
    payload = f"{candidate.title}|{candidate.description}|{candidate.ask:.2f}"
    return hashlib.sha256(payload.encode()).hexdigest()


class SharedDict(Protocol):
    def get(self, key: str) -> Any: ...

    def put(self, key: str, value: Any) -> None: ...

    def __contains__(self, key: object) -> bool: ...

    def __getitem__(self, key: str) -> Any: ...

    def __setitem__(self, key: str, value: Any) -> None: ...

    def pop(self, key: str, default: Any = None) -> Any: ...


@dataclass
class _Entry:
    result: ScoreResult
    expires_at: float


class EstimateCache:
    """Local memory with optional write-through to a shared Modal Dict."""

    def __init__(self, ttl_days: int = 14, shared: SharedDict | None = None) -> None:
        self._ttl = ttl_days * 86400
        self._local: dict[str, _Entry] = {}
        self._shared = shared

    def get(self, key: str) -> ScoreResult | None:
        now = time.time()
        entry = self._local.get(key)
        if entry is not None:
            if now > entry.expires_at:
                del self._local[key]
            else:
                return entry.result.model_copy(update={"cached": True})

        if self._shared is None:
            return None
        try:
            raw = self._shared[key]
        except KeyError:
            return None
        except Exception as exc:  # noqa: BLE001 — Dict may be unavailable offline
            log.warning("shared get failed: %s", exc)
            return None

        expires_at = float(raw.get("expires_at", 0))
        if now > expires_at:
            try:
                self._shared.pop(key, None)
            except Exception:  # noqa: BLE001
                pass
            return None
        result = ScoreResult.model_validate(raw["result"])
        self._local[key] = _Entry(result=result, expires_at=expires_at)
        return result.model_copy(update={"cached": True})

    def put(self, key: str, result: ScoreResult) -> None:
        stored = result.model_copy(update={"cached": False, "content_hash": key})
        expires_at = time.time() + self._ttl
        self._local[key] = _Entry(result=stored, expires_at=expires_at)
        if self._shared is None:
            return
        try:
            self._shared[key] = {
                "result": stored.model_dump(mode="json"),
                "expires_at": expires_at,
            }
        except Exception as exc:  # noqa: BLE001
            log.warning("shared put failed: %s", exc)

    def clear(self) -> None:
        self._local.clear()


def build_estimate_cache(ttl_days: int, *, use_modal_dict: bool, modal_app: str) -> EstimateCache:
    shared = None
    if use_modal_dict:
        try:
            import modal

            name = f"{modal_app}-estimate-cache"
            shared = modal.Dict.from_name(name, create_if_missing=True)
            log.info("using Modal Dict cache name=%s", name)
        except Exception as exc:  # noqa: BLE001
            log.warning("Modal Dict unavailable (%s); falling back to memory", exc)
    return EstimateCache(ttl_days=ttl_days, shared=shared)
