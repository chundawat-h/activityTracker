"""
Entry point for the Activity Tracking Pipeline.

Usage:
    python main.py            # initializes the DB, then starts the scheduler (blocking)
    python main.py --once     # runs the pipeline a single time and exits (useful for cron/testing)
"""

from __future__ import annotations

import argparse
import sys

from backend.config.logging_config import configure_logging, get_logger
from backend.database.session import init_db
from backend.scheduler.scheduler import start_scheduler
from backend.services.pipeline import run_pipeline

logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Chalo Activity Tracking Pipeline")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the pipeline a single time and exit, instead of starting the scheduler.",
    )
    args = parser.parse_args()

    configure_logging()
    logger.info("initializing_database")
    init_db()

    if args.once:
        logger.info("running_pipeline_once")
        run_pipeline()
        return 0

    start_scheduler()
    return 0


if __name__ == "__main__":
    sys.exit(main())
