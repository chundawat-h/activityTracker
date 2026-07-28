"""
Scheduling layer — runs the pipeline on a configurable interval.

SCRAPE_INTERVAL_MINUTES controls the interval directly (e.g. 60 for hourly,
1440 for daily). Using APScheduler's IntervalTrigger means any future
requirement for a more dynamic schedule (cron-style, per-source intervals,
etc.) is a small change here, not a rewrite — swap IntervalTrigger for
CronTrigger, or register multiple jobs, without touching the pipeline.
"""

from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.config.logging_config import get_logger
from backend.config.settings import settings
from backend.services.pipeline import run_pipeline

logger = get_logger(__name__)


def _job() -> None:
    logger.info("scheduled_job_starting")
    try:
        run_pipeline()
    except Exception:
        logger.exception("scheduled_job_failed")


def start_scheduler() -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        _job,
        trigger=IntervalTrigger(minutes=settings.scrape_interval_minutes),
        id="activity_tracker_pipeline",
        max_instances=1,  # never overlap two scrapes of the same run
        coalesce=True,  # if a run was missed (e.g. downtime), only run once on catch-up
    )

    logger.info(
        "scheduler_starting",
        extra={"interval_minutes": settings.scrape_interval_minutes},
    )

    if settings.run_scrape_on_startup:
        _job()

    scheduler.start()
