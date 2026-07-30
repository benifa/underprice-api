"""LLM Judge — Phase 5. Stub accepts without calling a provider."""

from __future__ import annotations

from underprice.logging_setup import agent_logger
from underprice.models import Candidate, Signal

log = agent_logger("LLMJudge")


class LlmJudgeSpecialist:
    name = "judge"

    def estimate(self, candidate: Candidate) -> Signal:
        log.info("stub — judge skipped")
        return Signal(
            source=self.name,
            value=None,
            notes="stub: judge not enabled",
            meta={"accepted": True},
        )
