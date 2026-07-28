"""
Normalizes raw ScrapedArticle objects into clean, consistent data before
they hit the matcher/database layer — trimming whitespace, enforcing
column-length limits, and deriving a summary when the source didn't
provide one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.scraper.base import ScrapedArticle

TITLE_MAX_LEN = 1024
URL_MAX_LEN = 1024
SUMMARY_MAX_LEN = 500


@dataclass
class ParsedArticle:
    source: str
    url: str
    title: str
    published_date: str | None
    body: str | None
    summary: str | None


def _clean_text(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = re.sub(r"[ \t]+", " ", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip() or None


def _derive_summary(body: str | None, existing_summary: str | None) -> str | None:
    if existing_summary:
        summary = existing_summary.strip()
    elif body:
        summary = body.strip()
    else:
        return None
    if len(summary) > SUMMARY_MAX_LEN:
        summary = summary[: SUMMARY_MAX_LEN - 1].rsplit(" ", 1)[0] + "…"
    return summary


def parse_article(raw: ScrapedArticle) -> ParsedArticle | None:
    """Returns None if the article doesn't have the bare minimum (title + url)."""
    title = _clean_text(raw.title)
    url = (raw.url or "").strip()

    if not title or not url:
        return None

    body = _clean_text(raw.body)
    summary = _derive_summary(body, _clean_text(raw.summary))

    return ParsedArticle(
        source=raw.source,
        url=url[:URL_MAX_LEN],
        title=title[:TITLE_MAX_LEN],
        published_date=_clean_text(raw.published_date),
        body=body,
        summary=summary,
    )


def parse_articles(raw_articles: list[ScrapedArticle]) -> list[ParsedArticle]:
    parsed = []
    for raw in raw_articles:
        article = parse_article(raw)
        if article is not None:
            parsed.append(article)
    return parsed
