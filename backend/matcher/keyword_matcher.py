"""
Keyword matching against parsed articles.

Keywords are loaded from keywords.csv (path configurable via
KEYWORDS_CSV_PATH) — never hardcoded — so business users can add or remove
tracked entities without touching code. Matching is case-insensitive and
one article can match any number of keywords.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from backend.config.logging_config import get_logger
from backend.config.settings import settings

logger = get_logger(__name__)


@dataclass(frozen=True)
class Keyword:
    text: str
    category: str | None
    pattern: re.Pattern


@dataclass
class KeywordMatchResult:
    keyword: str
    category: str | None


def _compile_pattern(keyword_text: str) -> re.Pattern:
    """
    Case-insensitive match. Uses word boundaries when the keyword is a
    "plain word" token (letters/digits/spaces only) to avoid matching
    inside unrelated longer words (e.g. keyword "IAS" should not match
    inside "BIAS"). Keywords containing punctuation (initials, parentheses,
    apostrophes — common in officer names like "S. Prakash (I.A.S.)") are
    matched as a literal, whitespace-flexible substring instead, since
    strict word boundaries around punctuation are unreliable.
    """
    escaped = re.escape(keyword_text.strip())
    # Allow flexible whitespace (single space vs multiple) between tokens.
    escaped = escaped.replace(r"\ ", r"\s+")

    if re.fullmatch(r"[A-Za-z0-9\s]+", keyword_text.strip()):
        pattern = rf"\b{escaped}\b"
    else:
        pattern = escaped

    return re.compile(pattern, re.IGNORECASE)


def load_keywords(csv_path: str | None = None) -> list[Keyword]:
    path = Path(csv_path or settings.keywords_csv_path)
    if not path.exists():
        raise FileNotFoundError(
            f"keywords.csv not found at {path}. Set KEYWORDS_CSV_PATH or place "
            f"the file at the project root."
        )

    keywords: list[Keyword] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "keyword" not in reader.fieldnames:
            raise ValueError("keywords.csv must have a 'keyword' column (and optional 'category').")

        for row in reader:
            text = (row.get("keyword") or "").strip()
            if not text:
                continue
            category = (row.get("category") or "").strip() or None
            keywords.append(Keyword(text=text, category=category, pattern=_compile_pattern(text)))

    logger.info("keywords_loaded", extra={"count": len(keywords), "path": str(path)})
    return keywords


@lru_cache(maxsize=1)
def _cached_keywords() -> tuple[Keyword, ...]:
    return tuple(load_keywords())


def get_keywords(force_reload: bool = False) -> list[Keyword]:
    """
    Returns the loaded keyword list, cached in-process. Pass force_reload=True
    (e.g. after a business user edits keywords.csv and the scheduler wants to
    pick it up on the next run) to bypass the cache.
    """
    if force_reload:
        _cached_keywords.cache_clear()
    return list(_cached_keywords())


def match_keywords(text: str, keywords: list[Keyword] | None = None) -> list[KeywordMatchResult]:
    """Returns every keyword found in `text` (title + body should be concatenated by the caller)."""
    if not text:
        return []
    active_keywords = keywords if keywords is not None else get_keywords()

    matches = []
    for kw in active_keywords:
        if kw.pattern.search(text):
            matches.append(KeywordMatchResult(keyword=kw.text, category=kw.category))
    return matches
