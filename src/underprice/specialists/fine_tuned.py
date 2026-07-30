"""FineTunedListPrice — Hub PEFT via local heuristic or Modal GPU.

Local path uses a deterministic heuristic so Phase 1 API/tests run without GPU.
Production sets UNDERPRICE_USE_MODAL_GPU=true and calls Modal .remote().
"""

from __future__ import annotations

import hashlib
import re

from underprice.config import Settings
from underprice.logging_setup import agent_logger
from underprice.models import Candidate, Signal

log = agent_logger("FineTuned")

# Consumer contract matches price-engine publish docs.
PRICE_PREFIX = "Price is $"
LIST_QUESTION = "What does this cost to the nearest dollar?"


def list_price_prompt(text: str) -> str:
    return f"{LIST_QUESTION}\n\n{text}\n\n{PRICE_PREFIX}"


class FineTunedListPriceSpecialist:
    name = "fine_tuned"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def estimate(self, candidate: Candidate) -> Signal:
        prompt = list_price_prompt(candidate.text_for_pricing())
        if self.settings.use_modal_gpu:
            value = self._via_modal(prompt)
            backend = "modal"
        else:
            value = self._local_heuristic(candidate)
            backend = "local_heuristic"
        log.info(
            "estimate=%.2f backend=%s revision=%s",
            value,
            backend,
            self.settings.adapter_revision,
        )
        return Signal(
            source=self.name,
            value=value,
            notes=f"backend={backend}",
            meta={
                "backend": backend,
                "adapter_id": self.settings.adapter_id,
                "revision": self.settings.adapter_revision,
                "base_model": self.settings.base_model,
            },
        )

    def _via_modal(self, prompt: str) -> float:
        # Import lazily so CPU web image never needs torch/modal at import time.
        import modal

        fn = modal.Function.from_name(self.settings.modal_app, "price_one")
        raw = fn.remote(prompt)
        return float(raw)

    def _local_heuristic(self, candidate: Candidate) -> float:
        """Stable stand-in until Modal GPU is wired. Not for production estimates."""
        # Prefer explicit dollar mentions in description as weak prior.
        text = candidate.text_for_pricing()
        mentioned = _first_dollar(text)
        if mentioned is not None:
            # Bias toward "list" slightly above ask when paste includes MSRP-like text.
            return max(1.0, min(999.0, mentioned))

        digest = hashlib.sha256(text.encode()).hexdigest()
        # Map hash → [$15, $400] band so tests are deterministic per title.
        bucket = int(digest[:8], 16) % 386
        return float(15 + bucket)


def _first_dollar(text: str) -> float | None:
    match = re.search(r"\$\s*(\d+(?:\.\d{1,2})?)", text)
    if not match:
        return None
    value = float(match.group(1))
    if 1.0 <= value <= 999.0:
        return value
    return None
