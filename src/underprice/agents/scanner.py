"""Scanner — DealNews RSS ingest (Ed week-8 pattern). Must not call GPU or Judge."""

from __future__ import annotations

from pydantic import BaseModel, Field

from underprice.agents.base import Agent
from underprice.config import Settings
from underprice.ingest.rss import DealNewsScraper, ScrapedDeal, extract_ask_price
from underprice.models import Candidate


class _SelectedDeal(BaseModel):
    product_description: str = Field(
        description="3-4 sentence product summary; focus on the item, not the coupon."
    )
    price: float = Field(description="Actual ask price as a number, not the discount amount.")
    url: str


class _DealSelection(BaseModel):
    deals: list[_SelectedDeal] = Field(description="Up to 5 deals with clear prices.")


class ScannerAgent(Agent):
    name = "Scanner"

    SYSTEM_PROMPT = (
        "You identify and summarize the most detailed deals from a list, selecting deals "
        "that have the most detailed, high quality description and the most clear price. "
        "Respond strictly in the schema. If the price isn't clear, omit the deal. "
        "Be careful with '$XXX off' or 'reduced by $XXX' — that is not the product price."
    )

    def __init__(self, settings: Settings, scraper: DealNewsScraper | None = None) -> None:
        super().__init__()
        self.settings = settings
        self.scraper = scraper or DealNewsScraper(
            feeds=settings.rss_feeds,
            max_entries_per_feed=settings.max_entries_per_feed,
            http_timeout_seconds=settings.http_timeout_seconds,
        )

    def scan(self, exclude_urls: list[str] | None = None) -> list[Candidate]:
        scraped = self.scraper.fetch(exclude_urls=exclude_urls)
        self.log.info("fetched scraped=%d", len(scraped))
        if not scraped:
            return []

        if self.settings.openai_api_key and self.settings.use_scanner_llm:
            candidates = self._select_with_llm(scraped)
        else:
            candidates = self._select_heuristic(scraped)

        limit = self.settings.max_scan_candidates
        selected = candidates[:limit]
        self.log.info("selected candidates=%d", len(selected))
        return selected

    def _select_heuristic(self, scraped: list[ScrapedDeal]) -> list[Candidate]:
        out: list[Candidate] = []
        for deal in scraped:
            ask = extract_ask_price(deal.text_blob())
            if ask is None:
                continue
            out.append(
                Candidate(
                    title=deal.title,
                    description=f"{deal.details.strip()}\n{deal.features.strip()}".strip(),
                    ask=ask,
                    url=deal.url,
                    category=deal.category,
                    source="dealnews",
                )
            )
        return out

    def _select_with_llm(self, scraped: list[ScrapedDeal]) -> list[Candidate]:
        try:
            from openai import OpenAI
        except ImportError:
            self.log.warning("openai package missing; falling back to heuristic")
            return self._select_heuristic(scraped)

        by_url = {d.url: d for d in scraped}
        user_prompt = (
            "Respond with the most promising deals from this list, selecting those with "
            "the most detailed product description and a clear price > 0. Rephrase each "
            "description as a product summary (not deal terms). Include at most 5 deals.\n\n"
            "Deals:\n\n" + "\n\n".join(d.describe() for d in scraped)
        )
        client = OpenAI(api_key=self.settings.openai_api_key)
        self.log.info("calling scanner LLM model=%s", self.settings.scanner_model)
        parsed = client.chat.completions.parse(
            model=self.settings.scanner_model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=_DealSelection,
        )
        selection = parsed.choices[0].message.parsed
        if selection is None:
            return self._select_heuristic(scraped)

        out: list[Candidate] = []
        for item in selection.deals:
            if item.price <= 0 or item.url not in by_url:
                continue
            scraped_deal = by_url[item.url]
            out.append(
                Candidate(
                    title=scraped_deal.title,
                    description=item.product_description,
                    ask=float(item.price),
                    url=item.url,
                    category=scraped_deal.category,
                    source="dealnews",
                )
            )
        return out or self._select_heuristic(scraped)
