"""Structured logging with agent/specialist identity on the record."""

from __future__ import annotations

import logging
import sys


class AgentFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        agent = getattr(record, "agent", "-")
        record.msg = f"[{agent}] {record.msg}"
        return super().format(record)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        AgentFormatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    )
    root.addHandler(handler)
    root.setLevel(level)


def agent_logger(name: str) -> logging.LoggerAdapter:
    return logging.LoggerAdapter(logging.getLogger(name), {"agent": name})
