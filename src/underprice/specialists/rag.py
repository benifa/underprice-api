"""RAG comps specialist — Phase 4. Stub returns no signal."""

from __future__ import annotations

from underprice.logging_setup import agent_logger
from underprice.models import Candidate, Signal

log = agent_logger("RAGComps")


class RagCompsSpecialist:
    name = "rag"

    def estimate(self, candidate: Candidate) -> Signal:
        log.info("stub — no vectorstore yet")
        return Signal(source=self.name, value=None, notes="stub: rag not enabled")
