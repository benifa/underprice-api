"""Messenger — Phase 3 FCM. Must not call GPU."""

from __future__ import annotations

from underprice.agents.base import Agent
from underprice.models import Candidate, ScoreResult


class MessengerAgent(Agent):
    name = "Messenger"

    def notify(self, candidate: Candidate, result: ScoreResult) -> bool:
        self.log.info(
            "stub notify candidate=%s deal_score=%s",
            candidate.id[:8],
            result.deal_score,
        )
        return False
