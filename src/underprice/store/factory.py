"""Pick Memory vs Postgres from settings — agents never care which."""

from __future__ import annotations

from underprice.config import Settings
from underprice.logging_setup import agent_logger
from underprice.store.memory import MemoryStore
from underprice.store.postgres import PostgresStore

log = agent_logger("Store")


def create_store(settings: Settings) -> MemoryStore | PostgresStore:
    url = (settings.database_url or "").strip()
    if not url:
        log.info("using MemoryStore (no DATABASE_URL)")
        return MemoryStore()
    log.info("using PostgresStore")
    return PostgresStore(url)
