"""Runtime settings. Secrets stay in env / Modal Secrets — never in code."""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="UNDERPRICE_",
        extra="ignore",
        populate_by_name=True,
    )

    env: str = "dev"
    log_level: str = "INFO"
    auth_secret: str = "dev-only-secret"

    adapter_id: str = "benifa/list-price-qlora"
    adapter_revision: str = "v0.1.0"
    base_model: str = "meta-llama/Llama-3.2-3B"

    median_gate: float = Field(default=0.95, description="ask/median <= this → continue")
    hot_deal: float = Field(default=0.70, description="ask/fair <= this → messenger-eligible")
    gray_zone_low: float = 0.70
    gray_zone_high: float = 0.90
    cache_ttl_days: int = 14

    modal_app: str = "underprice"
    use_modal_gpu: bool = False
    use_modal_dict: bool = False

    # Postgres (Neon/Supabase). Empty → MemoryStore.
    database_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "UNDERPRICE_DATABASE_URL",
            "DATABASE_URL",
            "database_url",
        ),
    )

    # Global category median fallback when store has too few samples
    default_category_median: float = 120.0
    median_min_samples: int = 5

    # Scanner / DealNews RSS (Ed week-8 sources)
    rss_feeds: list[str] = Field(
        default_factory=lambda: [
            "https://www.dealnews.com/c142/Electronics/?rss=1",
            "https://www.dealnews.com/c39/Computers/?rss=1",
            "https://www.dealnews.com/f1912/Smart-Home/?rss=1",
        ]
    )
    max_entries_per_feed: int = 10
    max_scan_candidates: int = 5
    http_timeout_seconds: float = 15.0
    use_scanner_llm: bool = True
    scanner_model: str = "gpt-4o-mini"
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "UNDERPRICE_OPENAI_API_KEY",
            "OPENAI_API_KEY",
            "openai_api_key",
        ),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
