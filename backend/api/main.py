"""
FastAPI application that powers the web dashboard.

Exposes REST endpoints to:
  - List / add / delete tracked keywords
  - Read / update the notification email address
  - Manually trigger a single pipeline run
  - Return the latest pipeline run stats

The FastAPI app is started from main.py and runs alongside the APScheduler
background scheduler via a lifespan handler.
"""

from __future__ import annotations

import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr

from backend.config.logging_config import get_logger
from backend.config.settings import settings, update_notification_email
from backend.database.session import init_db
from backend.matcher.keyword_matcher import add_keyword, delete_keyword, list_keywords_raw
from backend.scheduler.scheduler import start_scheduler
from backend.services.pipeline import run_pipeline

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# App + lifespan
# ---------------------------------------------------------------------------

app = FastAPI(title="Activity Tracker Dashboard", version="1.0.0")

_scheduler_started = False


@app.on_event("startup")
def on_startup() -> None:
    global _scheduler_started
    init_db()
    if not _scheduler_started:
        _scheduler_started = True
        # Run the scheduler in a daemon thread so it doesn't block uvicorn
        t = threading.Thread(target=start_scheduler, daemon=True)
        t.start()
        logger.info("scheduler_thread_started")


# ---------------------------------------------------------------------------
# Static frontend (served at /)
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@app.get("/", include_in_schema=False)
def serve_index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class KeywordIn(BaseModel):
    keyword: str
    category: str = ""


class EmailIn(BaseModel):
    email: str


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/api/keywords")
def get_keywords_route():
    """Return all tracked keywords."""
    return list_keywords_raw()


@app.post("/api/keywords", status_code=201)
def add_keyword_route(body: KeywordIn):
    """Add a new keyword / person to track."""
    try:
        add_keyword(body.keyword, body.category or None)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "created", "keyword": body.keyword}


@app.delete("/api/keywords/{keyword}")
def delete_keyword_route(keyword: str):
    """Remove a keyword from tracking."""
    deleted = delete_keyword(keyword)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Keyword '{keyword}' not found.")
    return {"status": "deleted", "keyword": keyword}


@app.get("/api/settings")
def get_settings_route():
    """Return current notification email settings."""
    return {
        "notification_email_to": settings.notification_email_to,
        "notification_email_from": settings.notification_email_from,
        "scrape_interval_minutes": settings.scrape_interval_minutes,
    }


@app.post("/api/settings/email")
def update_email_route(body: EmailIn):
    """Update the notification email address."""
    try:
        update_notification_email(body.email)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "updated", "email": body.email}


@app.post("/api/pipeline/run")
def trigger_pipeline_route():
    """Manually trigger one pipeline run (runs synchronously, may be slow)."""
    logger.info("manual_pipeline_trigger")
    stats = run_pipeline()
    return {"status": "completed", "stats": [s.__dict__ for s in stats]}
