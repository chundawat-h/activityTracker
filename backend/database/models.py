"""
ORM models.

Article       -> one row per scraped article (source of truth for dedup).
KeywordMatch  -> one row per (article, matched keyword) pair.

Dedup strategy (see FUNCTIONAL REQUIREMENTS #4):
  - `url` is unique -> the fastest, most reliable dedup key.
  - `title_hash` is also stored & indexed as a fallback, in case the same
    article is republished under a different URL (common on these sites
    when content gets re-indexed).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


def compute_title_hash(title: str) -> str:
    normalized = " ".join(title.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("url", name="uq_articles_url"),
        Index("ix_articles_title_hash", "title_hash"),
        Index("ix_articles_source", "source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    title_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    published_date: Mapped[str | None] = mapped_column(String(100), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    has_keyword_match: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    keyword_matches: Mapped[list["KeywordMatch"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Article id={self.id} source={self.source!r} title={self.title[:40]!r}>"


class KeywordMatch(Base):
    __tablename__ = "keyword_matches"
    __table_args__ = (
        UniqueConstraint("article_id", "keyword", name="uq_keyword_match_article_keyword"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), nullable=False)

    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)

    article: Mapped["Article"] = relationship(back_populates="keyword_matches")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<KeywordMatch article_id={self.article_id} keyword={self.keyword!r}>"
