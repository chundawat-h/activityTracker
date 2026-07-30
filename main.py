"""
Entry point for the Activity Tracking Pipeline.

Usage:
    python main.py            # start the web dashboard + background scheduler (http://localhost:8000)
    python main.py --once     # run the pipeline a single time and exit (useful for cron/testing)
    python main.py --host 0.0.0.0 --port 8080  # custom bind address / port
"""

from __future__ import annotations

import argparse
import sys

from backend.config.logging_config import configure_logging, get_logger

logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Chalo Activity Tracking Pipeline")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the pipeline a single time and exit (no web server).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for the web server.")
    parser.add_argument("--port", type=int, default=8000, help="Port for the web server.")
    args = parser.parse_args()

    configure_logging()

    if args.once:
        # Lightweight mode: just run the pipeline once and exit
        from backend.config.logging_config import get_logger as _gl
        from backend.database.session import init_db
        from backend.services.pipeline import run_pipeline

        logger.info("initializing_database")
        init_db()
        logger.info("running_pipeline_once")
        run_pipeline()
        return 0

    # Default mode: start the FastAPI web server (which also starts the scheduler)
    import uvicorn

    logger.info("starting_web_server", extra={"host": args.host, "port": args.port})
    uvicorn.run(
        "backend.api.main:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_config=None,  # we use our own structured logger
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
