"""Local developer CLI."""

from __future__ import annotations

import json

import typer
import uvicorn

from underprice.agents.ensemble import EnsembleAgent
from underprice.agents.messenger import MessengerAgent
from underprice.agents.planner import PlannerAgent
from underprice.agents.scanner import ScannerAgent
from underprice.config import get_settings
from underprice.logging_setup import configure_logging
from underprice.models import Candidate
from underprice.store.factory import create_store

app = typer.Typer(help="Underprice API developer tools", no_args_is_help=True)


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = True) -> None:
    """Run the FastAPI app locally."""
    uvicorn.run("underprice.api.app:app", host=host, port=port, reload=reload)


@app.command("score-once")
def score_once(
    title: str = typer.Option(...),
    ask: float = typer.Option(...),
    description: str = typer.Option(""),
    category: str | None = typer.Option(None),
) -> None:
    """Score one paste candidate without standing up HTTP."""
    settings = get_settings()
    configure_logging(settings.log_level)
    ensemble = EnsembleAgent(settings)
    result = ensemble.score(
        Candidate(title=title, description=description, ask=ask, category=category)
    )
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))


@app.command()
def hunt(limit: int = typer.Option(5, help="Max candidates to score this tick")) -> None:
    """One hunt tick: DealNews RSS → Ensemble → persist hot deals."""
    base = get_settings()
    settings = base.model_copy(update={"max_scan_candidates": limit})
    configure_logging(settings.log_level)
    store = create_store(settings)
    planner = PlannerAgent(
        ScannerAgent(settings),
        EnsembleAgent(settings, store=store),
        MessengerAgent(),
        store=store,
    )
    results = planner.hunt_tick()
    summary = {
        "scanned": len(results),
        "hot": sum(1 for r in results if r.messenger_eligible),
        "results": [
            {
                "ask": r.ask,
                "fair_value": r.fair_value,
                "deal_score": r.deal_score,
                "messenger_eligible": r.messenger_eligible,
                "stages_run": r.stages_run,
                "early_exit_reason": r.early_exit_reason,
            }
            for r in results
        ],
    }
    typer.echo(json.dumps(summary, indent=2))


if __name__ == "__main__":
    app()
