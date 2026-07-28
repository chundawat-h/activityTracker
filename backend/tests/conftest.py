# ruff: noqa: I001  (import order here is intentional — env vars must be
# set before backend modules are imported, since settings.py reads them
# at import time)
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("COMPOSIO_API_KEY", "test-key")
os.environ.setdefault("KEYWORDS_CSV_PATH", str(
    __import__("pathlib").Path(__file__).resolve().parent / "fixtures" / "test_keywords.csv"
))

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.database.base import Base  # noqa: E402
from backend.database import models  # noqa: E402, F401 (ensure models registered)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
