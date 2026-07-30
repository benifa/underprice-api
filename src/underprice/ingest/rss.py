"""DealNews RSS ingest — same sources as Ed Donner's week-8 scanner.

Allowlisted feeds only. Per-entry failures are skipped (do not kill the run).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import feedparser
import requests
from bs4 import BeautifulSoup

log = logging.getLogger("underprice.ingest.rss")

# Ed's default DealNews category feeds (course week 8).
DEFAULT_FEEDS: list[str] = [
    "https://www.dealnews.com/c142/Electronics/?rss=1",
    "https://www.dealnews.com/c39/Computers/?rss=1",
    "https://www.dealnews.com/f1912/Smart-Home/?rss=1",
]

_FEED_CATEGORY: dict[str, str] = {
    "c142": "electronics",
    "c39": "electronics",
    "f1912": "home",
}

MAX_TITLE = 100
MAX_SECTION = 500


def _category_from_feed(feed_url: str) -> str:
    for key, cat in _FEED_CATEGORY.items():
        if key in feed_url:
            return cat
    return "electronics"


def _clean_snippet(html_snippet: str) -> str:
    soup = BeautifulSoup(html_snippet, "html.parser")
    snippet_div = soup.find("div", class_="snippet summary")
    if snippet_div:
        description = snippet_div.get_text(strip=True)
        description = BeautifulSoup(description, "html.parser").get_text()
        description = re.sub("<[^<]+?>", "", description)
        result = description.strip()
    else:
        result = html_snippet
    return result.replace("\n", " ")


def extract_ask_price(text: str) -> float | None:
    """Heuristic ask price when Scanner LLM is off.

    Prefer absolute prices; skip '$X off' / 'save $X' discount phrasing.
    """
    lowered = text.lower()
    # "for $199" / "now $49.99"
    for pattern in (
        r"(?:for|now|only|price[:\s]+)\s*\$\s*(\d+(?:\.\d{1,2})?)",
        r"\$\s*(\d+(?:\.\d{1,2})?)\s*(?:shipped|delivered)?\b",
    ):
        for match in re.finditer(pattern, lowered):
            start = max(0, match.start() - 12)
            window = lowered[start : match.end() + 8]
            if re.search(r"\b(?:off|save|rebate|discount)\b", window):
                continue
            value = float(match.group(1))
            if 1.0 <= value <= 999.0:
                return value
    return None


@dataclass
class ScrapedDeal:
    title: str
    summary: str
    url: str
    details: str
    features: str
    category: str
    feed_url: str

    def describe(self) -> str:
        return (
            f"Title: {self.title}\n"
            f"Details: {self.details.strip()}\n"
            f"Features: {self.features.strip()}\n"
            f"URL: {self.url}"
        )

    def text_blob(self) -> str:
        return f"{self.title}\n{self.summary}\n{self.details}\n{self.features}"


class DealNewsScraper:
    """Fetch DealNews (and configured) RSS entries and enrich from the deal page."""

    def __init__(
        self,
        feeds: list[str] | None = None,
        *,
        max_entries_per_feed: int = 10,
        http_timeout_seconds: float = 15.0,
    ) -> None:
        self.feeds = feeds or list(DEFAULT_FEEDS)
        self.max_entries_per_feed = max_entries_per_feed
        self.http_timeout_seconds = http_timeout_seconds

    def fetch(self, exclude_urls: list[str] | None = None) -> list[ScrapedDeal]:
        exclude = set(exclude_urls or [])
        deals: list[ScrapedDeal] = []
        for feed_url in self.feeds:
            feed = feedparser.parse(feed_url)
            if getattr(feed, "bozo", False) and not feed.entries:
                log.warning("feed unreadable url=%s", feed_url)
                continue
            category = _category_from_feed(feed_url)
            for entry in feed.entries[: self.max_entries_per_feed]:
                try:
                    links = entry.get("links") or []
                    url = links[0]["href"] if links else entry.get("link")
                    if not url or url in exclude:
                        continue
                    deals.append(
                        self._from_entry(
                            entry, url=url, category=category, feed_url=feed_url
                        )
                    )
                    time.sleep(0.05)
                except Exception:  # noqa: BLE001 — one bad entry must not kill the hunt
                    log.warning("skip malformed entry feed=%s", feed_url, exc_info=True)
        return deals

    def _from_entry(
        self,
        entry: dict,
        *,
        url: str,
        category: str,
        feed_url: str,
    ) -> ScrapedDeal:
        title = str(entry.get("title") or "")[:MAX_TITLE]
        summary = _clean_snippet(str(entry.get("summary") or ""))
        details, features = summary, ""
        try:
            resp = requests.get(url, timeout=self.http_timeout_seconds)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            content_section = soup.find("div", class_="content-section")
            if content_section:
                content = content_section.get_text()
                content = content.replace("\nmore", "").replace("\n", " ")
                if "Features" in content:
                    details, features = content.split("Features", 1)
                else:
                    details, features = content, ""
        except Exception:  # noqa: BLE001 — RSS summary is enough to continue
            log.warning("page enrich failed url=%s", url)

        return ScrapedDeal(
            title=title,
            summary=summary,
            url=url,
            details=details[:MAX_SECTION],
            features=features[:MAX_SECTION],
            category=category,
            feed_url=feed_url,
        )
