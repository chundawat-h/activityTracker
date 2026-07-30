"""
Shared scraper infrastructure.

Every site-specific scraper subclasses `BaseScraper` and implements
`scrape_articles()`, returning a list of `ScrapedArticle` objects. Keeping
this contract identical across sites is what lets the pipeline (parser ->
matcher -> dedup -> notifier) stay completely source-agnostic — adding a
third website later means writing one new scraper class, nothing else.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import cloudscraper
import requests

from backend.config.logging_config import get_logger
from backend.config.settings import settings

logger = get_logger(__name__)


@dataclass
class ScrapedArticle:
    """Raw article data as extracted from a source website, pre-parsing."""

    source: str
    url: str
    title: str
    published_date: str | None = None
    body: str | None = None
    summary: str | None = None


class ScraperError(Exception):
    """Raised when a scraper cannot complete its job (network, parsing, etc.)."""


class BaseScraper(ABC):
    #: Human-readable, stable identifier for this source (stored in DB).
    source_name: str = "unknown"

    def __init__(self) -> None:
        # cloudscraper mimics a real browser TLS fingerprint, bypassing
        # Cloudflare / WAF bot-detection (403s, JS challenges, etc.).
        # It is a drop-in replacement for requests.Session.
        self.session: requests.Session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        self.session.headers.update(
            {
                "User-Agent": settings.request_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def fetch_html(self, url: str, *, extra_headers: dict | None = None, verify: bool = True) -> str:
        """Fetch a URL and return raw HTML, raising ScraperError on failure."""
        try:
            response = self.session.get(
                url,
                timeout=settings.request_timeout_seconds,
                headers=extra_headers or {},
                verify=verify,
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            raise ScraperError(f"Failed to fetch {url}: {exc}") from exc

    def polite_delay(self, seconds: float = 1.0) -> None:
        """Small delay between requests to a single site, to be a good citizen."""
        time.sleep(seconds)

    @abstractmethod
    def scrape_articles(self) -> list[ScrapedArticle]:
        """Return the latest articles found on this source, newest first."""
        raise NotImplementedError

    def run(self) -> list[ScrapedArticle]:
        """Public entry point used by the pipeline — wraps scrape_articles with logging."""
        logger.info("scraping_started", extra={"source": self.source_name})
        try:
            articles = self.scrape_articles()
        except ScraperError:
            logger.exception("scraping_failed", extra={"source": self.source_name})
            raise
        logger.info(
            "scraping_completed",
            extra={"source": self.source_name, "articles_found": len(articles)},
        )
        return articles[: settings.max_articles_per_scrape]
