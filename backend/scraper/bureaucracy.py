"""
Scraper for indianbureaucracy.com/appointments/ (a standard WordPress site).

WordPress always wraps individual posts in an <article> tag (via the
`post_class()` template function) and renders full post bodies inside a
`.entry-content` div, regardless of theme — so we anchor on those two
generic, theme-independent hooks first, with a couple of theme-specific
fallbacks (this particular site uses a Divi-family theme) in case the
generic hooks come up empty.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from backend.config.logging_config import get_logger
from backend.scraper.base import BaseScraper, ScrapedArticle, ScraperError

logger = get_logger(__name__)

LISTING_URL = "https://www.indianbureaucracy.com/category/appointments/"

# Candidate CSS selectors, tried in order, for locating each post's title
# link within its <article> container. Kept as a list (not a single
# hardcoded selector) so a theme/markup change only requires editing this
# list, not the scraping logic itself.
TITLE_LINK_SELECTORS = [
    "h2.entry-title a",
    "h3.entry-title a",
    ".et_pb_post h2 a",
    "h2 a",
    "h3 a",
]

DATE_SELECTORS = [
    "span.published",
    "time.entry-date",
    "time",
    ".post-meta .date",
]

BODY_SELECTORS = [
    "div.entry-content",
    "div.et_pb_post_content",
    "article .post-content",
]


class IndianBureaucracyScraper(BaseScraper):
    source_name = "indianbureaucracy"

    def scrape_articles(self) -> list[ScrapedArticle]:
        html = self.fetch_html(LISTING_URL)
        soup = BeautifulSoup(html, "html.parser")

        articles_meta = self._parse_listing(soup)
        if not articles_meta:
            logger.warning(
                "no_articles_found_in_listing",
                extra={"source": self.source_name, "url": LISTING_URL},
            )
            return []

        results: list[ScrapedArticle] = []
        for meta in articles_meta:
            try:
                self.polite_delay(0.5)
                detail = self._scrape_detail(meta["url"])
            except ScraperError:
                logger.warning(
                    "detail_scrape_failed",
                    extra={"source": self.source_name, "url": meta["url"]},
                )
                detail = {"body": None, "summary": None}

            results.append(
                ScrapedArticle(
                    source=self.source_name,
                    url=meta["url"],
                    title=meta["title"],
                    published_date=meta.get("date"),
                    body=detail.get("body"),
                    summary=detail.get("summary"),
                )
            )
        return results

    # -- internals ---------------------------------------------------------

    def _parse_listing(self, soup: BeautifulSoup) -> list[dict]:
        items: list[dict] = []
        containers = soup.find_all("article")
        if not containers:
            # Fallback: Divi-style post wrappers that aren't <article> tags.
            containers = soup.select(".et_pb_post")

        for container in containers:
            title_tag = self._first_match(container, TITLE_LINK_SELECTORS)
            if title_tag is None or not title_tag.get("href"):
                continue

            title = title_tag.get_text(strip=True)
            url = title_tag["href"].strip()
            if not title or not url:
                continue

            date_tag = self._first_match(container, DATE_SELECTORS)
            date_text = date_tag.get_text(strip=True) if date_tag else None
            if date_tag is not None and date_tag.has_attr("datetime"):
                date_text = date_tag["datetime"]

            items.append({"title": title, "url": url, "date": date_text})

        # De-dupe by URL while preserving order (listing pages sometimes
        # repeat a featured post at the top and again in the main grid).
        seen: set[str] = set()
        deduped = []
        for item in items:
            if item["url"] not in seen:
                seen.add(item["url"])
                deduped.append(item)
        return deduped

    def _scrape_detail(self, url: str) -> dict:
        html = self.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        body_tag = self._first_match(soup, BODY_SELECTORS)
        if body_tag is None:
            return {"body": None, "summary": None}

        # Strip script/style noise, then collapse whitespace.
        for tag in body_tag.find_all(["script", "style"]):
            tag.decompose()

        paragraphs = [p.get_text(" ", strip=True) for p in body_tag.find_all("p")]
        paragraphs = [p for p in paragraphs if p]
        body = "\n\n".join(paragraphs) if paragraphs else body_tag.get_text(" ", strip=True)
        body = re.sub(r"\s+\n", "\n", body).strip()

        summary = paragraphs[0] if paragraphs else None
        return {"body": body or None, "summary": summary}

    @staticmethod
    def _first_match(node: Tag, selectors: list[str]) -> Tag | None:
        for selector in selectors:
            match = node.select_one(selector)
            if match is not None:
                return match
        return None
