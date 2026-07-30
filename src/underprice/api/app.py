"""ASGI entrypoint — CPU web image only (no torch)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from underprice import __version__
from underprice.api.deps import get_container
from underprice.api.routes import deals, devices, hunt, prefs, score
from underprice.api.schemas import HealthResponse
from underprice.logging_setup import configure_logging


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_dotenv(override=True)
    container = get_container()
    configure_logging(container.settings.log_level)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Underprice API",
        version=__version__,
        description="Modular agentic backend for Underprice deal scoring.",
        lifespan=lifespan,
    )
    app.include_router(score.router)
    app.include_router(deals.router)
    app.include_router(devices.router)
    app.include_router(prefs.router)
    app.include_router(hunt.router)

    @app.get("/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    return app


app = create_app()
