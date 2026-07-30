"""Composition root — wire agents once; routes stay thin."""

from __future__ import annotations

from dataclasses import dataclass

from underprice.agents.ensemble import EnsembleAgent
from underprice.agents.messenger import MessengerAgent
from underprice.agents.planner import PlannerAgent
from underprice.agents.scanner import ScannerAgent
from underprice.cache.estimate_cache import EstimateCache, build_estimate_cache
from underprice.config import Settings, get_settings
from underprice.store.factory import create_store
from underprice.store.memory import MemoryStore
from underprice.store.postgres import PostgresStore


@dataclass
class AppContainer:
    settings: Settings
    store: MemoryStore | PostgresStore | None = None
    cache: EstimateCache | None = None
    ensemble: EnsembleAgent | None = None
    planner: PlannerAgent | None = None

    def __post_init__(self) -> None:
        if self.store is None:
            self.store = create_store(self.settings)
        self.cache = self.cache or build_estimate_cache(
            self.settings.cache_ttl_days,
            use_modal_dict=self.settings.use_modal_dict,
            modal_app=self.settings.modal_app,
        )
        self.ensemble = self.ensemble or EnsembleAgent(
            self.settings,
            self.cache,
            store=self.store,
        )
        self.planner = self.planner or PlannerAgent(
            ScannerAgent(self.settings),
            self.ensemble,
            MessengerAgent(),
            store=self.store,
        )


_container: AppContainer | None = None


def get_container() -> AppContainer:
    global _container
    if _container is None:
        _container = AppContainer(settings=get_settings())
    return _container


def reset_container() -> None:
    """Test helper."""
    global _container
    _container = None
