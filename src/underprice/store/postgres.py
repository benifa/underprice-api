"""Postgres store — Neon/Supabase-ready. Used when UNDERPRICE_DATABASE_URL is set."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from underprice.models import Confidence, Deal, Prefs, ScoreJob, ScoreResult, Signal

_SCHEMA = """
CREATE TABLE IF NOT EXISTS deals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    ask DOUBLE PRECISION NOT NULL,
    url TEXT,
    fair_value DOUBLE PRECISION NOT NULL,
    deal_score DOUBLE PRECISION NOT NULL,
    confidence TEXT NOT NULL,
    signals JSONB NOT NULL DEFAULT '{}'::jsonb,
    stages_run JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS score_jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    stages JSONB NOT NULL DEFAULT '[]'::jsonb,
    result JSONB,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS prefs (
    install_id TEXT PRIMARY KEY,
    keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    categories JSONB NOT NULL DEFAULT '[]'::jsonb,
    min_score DOUBLE PRECISION NOT NULL DEFAULT 0.7,
    notify_enabled BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS devices (
    install_id TEXT PRIMARY KEY,
    fcm_token TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS price_samples (
    id BIGSERIAL PRIMARY KEY,
    category TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_deals_created_at ON deals (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_price_samples_category ON price_samples (category);
"""


class PostgresStore:
    def __init__(self, database_url: str) -> None:
        self._url = database_url
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(_SCHEMA)
            conn.commit()

    @contextmanager
    def _conn(self) -> Iterator[psycopg.Connection[Any]]:
        with psycopg.connect(self._url, row_factory=dict_row) as conn:
            yield conn

    def save_job(self, job: ScoreJob) -> ScoreJob:
        payload = job.model_dump(mode="json")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO score_jobs (
                    job_id, status, stages, result, error, created_at, updated_at
                ) VALUES (
                    %(job_id)s, %(status)s, %(stages)s, %(result)s,
                    %(error)s, %(created_at)s, %(updated_at)s
                )
                ON CONFLICT (job_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    stages = EXCLUDED.stages,
                    result = EXCLUDED.result,
                    error = EXCLUDED.error,
                    updated_at = EXCLUDED.updated_at
                """,
                {
                    "job_id": payload["job_id"],
                    "status": payload["status"],
                    "stages": Jsonb(payload["stages"]),
                    "result": Jsonb(payload["result"]) if payload["result"] is not None else None,
                    "error": payload["error"],
                    "created_at": payload["created_at"],
                    "updated_at": payload["updated_at"],
                },
            )
            conn.commit()
        return job

    def get_job(self, job_id: str) -> ScoreJob | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT job_id, status, stages, result, error, created_at, updated_at "
                "FROM score_jobs WHERE job_id = %s",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return ScoreJob.model_validate(row)

    def save_deal_from_score(
        self,
        title: str,
        description: str,
        url: str | None,
        result: ScoreResult,
    ) -> Deal | None:
        if result.fair_value is None or result.deal_score is None:
            return None
        if not result.messenger_eligible:
            return None
        deal = Deal(
            id=result.candidate_id,
            title=title,
            description=description,
            ask=result.ask,
            url=url,
            fair_value=result.fair_value,
            deal_score=result.deal_score,
            confidence=result.confidence,
            signals=result.signals,
            stages_run=result.stages_run,
        )
        payload = deal.model_dump(mode="json")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO deals (
                    id, title, description, ask, url, fair_value, deal_score,
                    confidence, signals, stages_run, created_at
                ) VALUES (
                    %(id)s, %(title)s, %(description)s, %(ask)s, %(url)s, %(fair_value)s,
                    %(deal_score)s, %(confidence)s, %(signals)s, %(stages_run)s, %(created_at)s
                )
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    ask = EXCLUDED.ask,
                    url = EXCLUDED.url,
                    fair_value = EXCLUDED.fair_value,
                    deal_score = EXCLUDED.deal_score,
                    confidence = EXCLUDED.confidence,
                    signals = EXCLUDED.signals,
                    stages_run = EXCLUDED.stages_run
                """,
                {
                    **payload,
                    "signals": Jsonb(payload["signals"]),
                    "stages_run": Jsonb(payload["stages_run"]),
                },
            )
            conn.commit()
        return deal

    def list_deals(self, *, cursor: int = 0, limit: int = 20) -> tuple[list[Deal], int | None]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, title, description, ask, url, fair_value, deal_score,
                       confidence, signals, stages_run, created_at
                FROM deals
                ORDER BY created_at DESC, id DESC
                OFFSET %s LIMIT %s
                """,
                (cursor, limit),
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) AS n FROM deals").fetchone()
        items = [_deal_from_row(r) for r in rows]
        n = int(total["n"]) if total else 0
        next_cursor = cursor + limit if cursor + limit < n else None
        return items, next_cursor

    def get_deal(self, deal_id: str) -> Deal | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT id, title, description, ask, url, fair_value, deal_score,
                       confidence, signals, stages_run, created_at
                FROM deals WHERE id = %s
                """,
                (deal_id,),
            ).fetchone()
        return _deal_from_row(row) if row else None

    def save_prefs(self, prefs: Prefs) -> Prefs:
        payload = prefs.model_dump(mode="json")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO prefs (
                    install_id, keywords, categories, min_score, notify_enabled
                ) VALUES (
                    %(install_id)s, %(keywords)s, %(categories)s,
                    %(min_score)s, %(notify_enabled)s
                )
                ON CONFLICT (install_id) DO UPDATE SET
                    keywords = EXCLUDED.keywords,
                    categories = EXCLUDED.categories,
                    min_score = EXCLUDED.min_score,
                    notify_enabled = EXCLUDED.notify_enabled
                """,
                {
                    "install_id": payload["install_id"],
                    "keywords": Jsonb(payload["keywords"]),
                    "categories": Jsonb(payload["categories"]),
                    "min_score": payload["min_score"],
                    "notify_enabled": payload["notify_enabled"],
                },
            )
            conn.commit()
        return prefs

    def get_prefs(self, install_id: str) -> Prefs | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT install_id, keywords, categories, min_score, notify_enabled "
                "FROM prefs WHERE install_id = %s",
                (install_id,),
            ).fetchone()
        return Prefs.model_validate(row) if row else None

    def register_device(self, install_id: str, fcm_token: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO devices (install_id, fcm_token)
                VALUES (%s, %s)
                ON CONFLICT (install_id) DO UPDATE SET fcm_token = EXCLUDED.fcm_token
                """,
                (install_id, fcm_token),
            )
            conn.commit()

    def record_price_sample(self, category: str, price: float) -> None:
        if price <= 0:
            return
        key = category.lower().strip() or "general"
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO price_samples (category, price) VALUES (%s, %s)",
                (key, float(price)),
            )
            conn.commit()

    def category_median(self, category: str, *, min_samples: int = 5) -> float | None:
        key = category.lower().strip() or "general"
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY price) AS median,
                       COUNT(*) AS n
                FROM price_samples
                WHERE category = %s
                """,
                (key,),
            ).fetchone()
        if row is None or int(row["n"]) < min_samples or row["median"] is None:
            return None
        return float(row["median"])

    def known_urls(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT url FROM deals WHERE url IS NOT NULL AND url <> ''"
            ).fetchall()
        return [str(r["url"]) for r in rows]


def _deal_from_row(row: dict[str, Any]) -> Deal:
    signals_raw = row.get("signals") or {}
    if isinstance(signals_raw, str):
        signals_raw = json.loads(signals_raw)
    signals = {
        k: Signal.model_validate(v) if not isinstance(v, Signal) else v
        for k, v in signals_raw.items()
    }
    stages = row.get("stages_run") or []
    if isinstance(stages, str):
        stages = json.loads(stages)
    return Deal(
        id=row["id"],
        title=row["title"],
        description=row.get("description") or "",
        ask=float(row["ask"]),
        url=row.get("url"),
        fair_value=float(row["fair_value"]),
        deal_score=float(row["deal_score"]),
        confidence=Confidence(row["confidence"]),
        signals=signals,
        stages_run=list(stages),
        created_at=row["created_at"],
    )
