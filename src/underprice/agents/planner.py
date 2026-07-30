"""Planner — orchestrates scan → score → notify. Does not price items itself."""

from __future__ import annotations

from typing import TYPE_CHECKING

from underprice.agents.base import Agent
from underprice.agents.ensemble import EnsembleAgent
from underprice.agents.messenger import MessengerAgent
from underprice.agents.scanner import ScannerAgent
from underprice.models import Candidate, ScoreResult

if TYPE_CHECKING:
    from underprice.store.base import Store


class PlannerAgent(Agent):
    name = "Planner"

    def __init__(
        self,
        scanner: ScannerAgent,
        ensemble: EnsembleAgent,
        messenger: MessengerAgent,
        store: Store | None = None,
    ) -> None:
        super().__init__()
        self.scanner = scanner
        self.ensemble = ensemble
        self.messenger = messenger
        self.store = store

    def hunt_tick(self) -> list[ScoreResult]:
        """Hunt: DealNews scan → Ensemble cascade → persist hot deals → notify."""
        self.log.info("hunt_tick start")
        exclude = self.store.known_urls() if self.store is not None else []
        candidates = self.scanner.scan(exclude_urls=exclude)
        results: list[ScoreResult] = []
        for candidate in candidates:
            result = self.ensemble.score(candidate)
            results.append(result)
            if self.store is not None:
                self.store.save_deal_from_score(
                    candidate.title,
                    candidate.description,
                    candidate.url,
                    result,
                )
            if result.messenger_eligible:
                self.messenger.notify(candidate, result)
        hot = sum(1 for r in results if r.messenger_eligible)
        self.log.info(
            "hunt_tick done candidates=%d scored=%d hot=%d",
            len(candidates),
            len(results),
            hot,
        )
        return results

    def score_on_demand(self, candidate: Candidate) -> ScoreResult:
        """Paste path — Planner may invoke Ensemble without Scanner."""
        return self.ensemble.score(candidate)
