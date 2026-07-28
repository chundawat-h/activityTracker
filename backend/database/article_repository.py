"""
Persistence layer for articles — this is where duplicate detection actually
happens (FUNCTIONAL REQUIREMENT #4): an article is considered a duplicate,
and is skipped, if either its exact URL or its title hash already exists in
the database.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config.logging_config import get_logger
from backend.database.models import Article, KeywordMatch, compute_title_hash
from backend.matcher.keyword_matcher import KeywordMatchResult
from backend.parser.article_parser import ParsedArticle

logger = get_logger(__name__)


def is_duplicate(session: Session, url: str, title: str) -> bool:
    title_hash = compute_title_hash(title)
    stmt = select(Article.id).where(
        (Article.url == url) | (Article.title_hash == title_hash)
    )
    return session.execute(stmt).first() is not None


def save_article(
    session: Session,
    parsed: ParsedArticle,
    matches: list[KeywordMatchResult],
) -> Article:
    article = Article(
        source=parsed.source,
        url=parsed.url,
        title=parsed.title,
        title_hash=compute_title_hash(parsed.title),
        published_date=parsed.published_date,
        body=parsed.body,
        summary=parsed.summary,
        processed_at=datetime.now(timezone.utc),
        has_keyword_match=bool(matches),
    )
    for m in matches:
        article.keyword_matches.append(KeywordMatch(keyword=m.keyword, category=m.category))

    session.add(article)
    session.flush()  # populate article.id without ending the transaction
    logger.info(
        "article_stored",
        extra={
            "article_id": article.id,
            "source": article.source,
            "url": article.url,
            "matched_keywords": [m.keyword for m in matches],
        },
    )
    return article


def mark_email_sent(session: Session, article: Article) -> None:
    article.email_sent = True
    article.email_sent_at = datetime.now(timezone.utc)
    session.add(article)
