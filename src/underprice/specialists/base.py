"""Specialist contract: estimate(candidate) -> Signal."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from underprice.models import Candidate, Signal


@runtime_checkable
class Specialist(Protocol):
    name: str

    def estimate(self, candidate: Candidate) -> Signal:
        """Return a pricing signal. value may be None on failure / no-op."""
        ...
