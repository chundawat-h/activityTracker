"""
Central configuration module.

All runtime configuration is loaded from environment variables (via a .env
file in development, or real environment variables in production/Render).
Nothing here is hardcoded — see .env.example for the full list of variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if present (no-op in production where real env vars exist)
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _get_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # --- Database -----------------------------------------------------
    # Defaults to a local SQLite file for development. Swap DATABASE_URL to
    # a Postgres URL (postgresql+psycopg2://...) for production — no code
    # changes required since we use SQLAlchemy.
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", f"sqlite:///{BASE_DIR / 'activity_tracker.db'}"
        )
    )

    # --- Composio (email notifications) --------------------------------
    composio_api_key: str = field(default_factory=lambda: os.getenv("COMPOSIO_API_KEY", ""))
    composio_connected_account_id: str = field(
        default_factory=lambda: os.getenv("COMPOSIO_CONNECTED_ACCOUNT_ID", "")
    )
    notification_email_to: str = field(
        default_factory=lambda: os.getenv("NOTIFICATION_EMAIL_TO", "")
    )
    notification_email_from: str = field(
        default_factory=lambda: os.getenv("NOTIFICATION_EMAIL_FROM", "")
    )

    # --- Scheduler -------------------------------------------------------
    scrape_interval_minutes: int = field(
        default_factory=lambda: _get_int("SCRAPE_INTERVAL_MINUTES", 60)
    )
    run_scrape_on_startup: bool = field(
        default_factory=lambda: _get_bool("RUN_SCRAPE_ON_STARTUP", True)
    )

    # --- Logging ---------------------------------------------------------
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # --- Keywords ----------------------------------------------------------
    keywords_csv_path: str = field(
        default_factory=lambda: os.getenv(
            "KEYWORDS_CSV_PATH", str(BASE_DIR / "keywords.csv")
        )
    )

    # --- Scraper behaviour -------------------------------------------------
    request_timeout_seconds: int = field(
        default_factory=lambda: _get_int("REQUEST_TIMEOUT_SECONDS", 20)
    )
    request_user_agent: str = field(
        default_factory=lambda: os.getenv(
            "REQUEST_USER_AGENT",
            "Mozilla/5.0 (compatible; ChaloActivityTracker/1.0; +https://chalo.com)",
        )
    )
    max_articles_per_scrape: int = field(
        default_factory=lambda: _get_int("MAX_ARTICLES_PER_SCRAPE", 50)
    )


settings = Settings()
