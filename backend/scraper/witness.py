"""
Scraper for witnessinthecorridors.com (a classic ASP.NET Web Forms site,
News.aspx?Id=2&index=1).

IMPORTANT — known limitation:
This site returns bot-detection errors to plain HTTP clients (verified during
development: a direct GET was blocked before any HTML was returned). Two
things follow from that, both handled below:

  1. We send full browser-like headers (see BaseScraper) and retry with
     backoff, which resolves this for a lot of basic bot filters. If the
     production environment still gets blocked, the fix is almost always
     one of: route requests through a residential/rotating proxy, or swap
     this scraper's `fetch_html` calls for a headless-browser fetch
     (e.g. Playwright) — the rest of the pipeline (parsing, matching,
     dedup, email) does not need to change either way.
  2. Because we could not inspect the live DOM while building this, the
     CSS selectors below are our best-effort based on how ASP.NET Web
     Forms "News.aspx" listing/detail pages are conventionally rendered
     (server controls emit predictable `ContentPlaceHolder`-prefixed IDs).
     They are intentionally kept in one place (SELECTOR CANDIDATES below)
     and ordered from most- to least-specific, with a generic fallback at
     the end, so a business user or engineer can fix scraping in minutes
     by inspecting the real page and adding/reordering one selector list —
     no changes needed anywhere else in the pipeline.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from backend.config.logging_config import get_logger
from backend.scraper.base import BaseScraper, ScrapedArticle, ScraperError

logger = get_logger(__name__)

BASE_URL = "https://www.witnessinthecorridors.com"
LISTING_URL = f"{BASE_URL}/News.aspx?Id=2&index=1"

# --- SELECTOR CANDIDATES (edit here if the live markup differs) -----------

LISTING_ITEM_SELECTORS = [
    "#ContentPlaceHolder1_rptNews a",
    ".news-list a",
    ".newsList a",
    "table a[href*='News.aspx']",
    "a[href*='News.aspx?Id']",
]

DETAIL_TITLE_SELECTORS = [
    "#ContentPlaceHolder1_lblTitle",
    "#ContentPlaceHolder1_lblNewsTitle",
    ".news-detail-title",
    "h1",
]

DETAIL_DATE_SELECTORS = [
    "#ContentPlaceHolder1_lblDate",
    "#ContentPlaceHolder1_lblNewsDate",
    ".news-detail-date",
    ".date",
]

DETAIL_BODY_SELECTORS = [
    "#ContentPlaceHolder1_lblNewsBody",
    "#ContentPlaceHolder1_lblDescription",
    "#ContentPlaceHolder1_lblBody",
    ".news-detail-body",
    ".newsBody",
]

# ---------------------------------------------------------------------------


class WitnessInTheCorridorsScraper(BaseScraper):
    source_name = "witnessinthecorridors"

    def scrape_articles(self) -> list[ScrapedArticle]:
        html = self.fetch_html(LISTING_URL)
        soup = BeautifulSoup(html, "html.parser")

        links = self._parse_listing(soup)
        if not links:
            logger.warning(
                "no_articles_found_in_listing",
                extra={"source": self.source_name, "url": LISTING_URL},
            )
            return []

        results: list[ScrapedArticle] = []
        for title, url in links:
            try:
                self.polite_delay(0.5)
                detail = self._scrape_detail(url)
            except ScraperError:
                logger.warning(
                    "detail_scrape_failed",
                    extra={"source": self.source_name, "url": url},
                )
                detail = {}

            results.append(
                ScrapedArticle(
                    source=self.source_name,
                    url=url,
                    title=detail.get("title") or title,
                    published_date=detail.get("date"),
                    body=detail.get("body"),
                    summary=detail.get("summary"),
                )
            )
        return results

    # -- internals ---------------------------------------------------------

    def _parse_listing(self, soup: BeautifulSoup) -> list[tuple[str, str]]:
        anchors: list[Tag] = []
        for selector in LISTING_ITEM_SELECTORS:
            anchors = soup.select(selector)
            if anchors:
                break

        results: list[tuple[str, str]] = []
        seen_urls: set[str] = set()
        for a in anchors:
            href = a.get("href", "").strip()
            title = a.get_text(strip=True)
            if not href or not title:
                continue
            if "news.aspx" not in href.lower():
                continue
            full_url = urljoin(BASE_URL, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            results.append((title, full_url))
        return results

    def _scrape_detail(self, url: str) -> dict:
        html = self.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        title_tag = self._first_match(soup, DETAIL_TITLE_SELECTORS)
        date_tag = self._first_match(soup, DETAIL_DATE_SELECTORS)
        body_tag = self._first_match(soup, DETAIL_BODY_SELECTORS)

        body = None
        summary = None
        if body_tag is not None:
            for tag in body_tag.find_all(["script", "style"]):
                tag.decompose()
            body = body_tag.get_text(" ", strip=True)
            body = re.sub(r"\s{2,}", " ", body).strip() or None
            if body:
                # First sentence (roughly) as a summary if the page doesn't
                # provide one explicitly.
                summary = re.split(r"(?<=[.!?])\s", body)[0][:400]

        return {
            "title": title_tag.get_text(strip=True) if title_tag else None,
            "date": date_tag.get_text(strip=True) if date_tag else None,
            "body": body,
            "summary": summary,
        }

    @staticmethod
    def _first_match(node: Tag, selectors: list[str]) -> Tag | None:
        for selector in selectors:
            match = node.select_one(selector)
            if match is not None:
                return match
        return None
