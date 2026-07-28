"""
Orchestrates a single end-to-end run of the pipeline:

    Scrape -> Parse -> Keyword match -> Duplicate check -> Store -> Notify

This is the single place that wires all the modules together. The
scheduler calls `run_pipeline()`; nothing else in the codebase needs to
know how the stages fit together.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.config.logging_config import get_logger
from backend.database.article_repository import is_duplicate, mark_email_sent, save_article
from backend.database.session import get_session
from backend.matcher.keyword_matcher import get_keywords, match_keywords
from backend.parser.article_parser import parse_articles
from backend.scraper.base import BaseScraper
from backend.scraper.bureaucracy import IndianBureaucracyScraper
from backend.scraper.witness import WitnessInTheCorridorsScraper
from backend.services.notification import AlertPayload, ComposioEmailNotifier, NotificationError

logger = get_logger(__name__)

# Registry of active scrapers. Adding a new source website later means
# adding one class here — nothing else in the pipeline changes.
SCRAPERS: list[type[BaseScraper]] = [
    IndianBureaucracyScraper,
    WitnessInTheCorridorsScraper,
]


@dataclass
class PipelineStats:
    source: str
    articles_found: int = 0
    articles_skipped_duplicate: int = 0
    articles_stored: int = 0
    articles_matched: int = 0
    emails_sent: int = 0
    errors: int = 0


def run_pipeline() -> list[PipelineStats]:
    all_stats: list[PipelineStats] = []
    keywords = get_keywords(force_reload=True)  # pick up keywords.csv edits between runs
    notifier: ComposioEmailNotifier | None = None
    try:
        notifier = ComposioEmailNotifier()
    except NotificationError:
        logger.warning("notifier_unavailable_alerts_will_not_be_emailed")

    for scraper_cls in SCRAPERS:
        stats = PipelineStats(source=scraper_cls.source_name)
        try:
            stats = _run_for_scraper(scraper_cls(), keywords, notifier)
        except Exception:
            logger.exception("pipeline_source_failed", extra={"source": scraper_cls.source_name})
            stats.errors += 1
        all_stats.append(stats)

    logger.info("pipeline_run_completed", extra={"stats": [s.__dict__ for s in all_stats]})
    return all_stats


def _run_for_scraper(scraper: BaseScraper, keywords, notifier: ComposioEmailNotifier | None) -> PipelineStats:
    stats = PipelineStats(source=scraper.source_name)

    raw_articles = scraper.run()
    stats.articles_found = len(raw_articles)

    parsed_articles = parse_articles(raw_articles)

    with get_session() as session:
        for parsed in parsed_articles:
            if is_duplicate(session, parsed.url, parsed.title):
                stats.articles_skipped_duplicate += 1
                logger.info(
                    "article_skipped_duplicate",
                    extra={"source": parsed.source, "url": parsed.url},
                )
                continue

            searchable_text = f"{parsed.title}\n{parsed.body or ''}"
            matches = match_keywords(searchable_text, keywords)

            article = save_article(session, parsed, matches)
            stats.articles_stored += 1

            if matches:
                stats.articles_matched += 1
                logger.info(
                    "matched_keywords",
                    extra={
                        "article_id": article.id,
                        "keywords": [m.keyword for m in matches],
                    },
                )
                if notifier is not None:
                    try:
                        notifier.send_alert(
                            AlertPayload(
                                article=article,
                                matched_keywords=[m.keyword for m in matches],
                                matched_categories=[m.category for m in matches if m.category],
                            )
                        )
                        mark_email_sent(session, article)
                        stats.emails_sent += 1
                    except NotificationError:
                        stats.errors += 1
                        # Article stays in the DB either way — dedup already
                        # happened, so we won't lose or double-process it;
                        # `email_sent` simply remains False for follow-up.

    return stats
