"""Agent base — identity for logs; no shared orchestration logic."""

from __future__ import annotations

from underprice.logging_setup import agent_logger


class Agent:
    name = "Agent"

    def __init__(self) -> None:
        self.log = agent_logger(self.name)
