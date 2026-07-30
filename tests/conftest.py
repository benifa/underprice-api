from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from underprice.api.app import create_app
from underprice.api.deps import AppContainer, reset_container
from underprice.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        env="test",
        use_modal_gpu=False,
        median_gate=0.95,
        hot_deal=0.70,
        cache_ttl_days=14,
        default_category_median=100.0,
    )


@pytest.fixture
def client(settings: Settings):
    reset_container()
    app = create_app()
    # Override composition root for tests
    from underprice.api import deps

    deps._container = AppContainer(settings=settings)
    with TestClient(app) as c:
        yield c
    reset_container()
