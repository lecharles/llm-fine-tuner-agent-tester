"""Shared fixtures for the S9 pytest suite (issue #12).

All tests here are hermetic: the backend lives on sys.path, the app home is a
tmp dir, and every provider/subprocess boundary is faked. Nothing in this
suite ever calls a real API or starts a real mlx_lm.server.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Isolate before any backend import: llmtuner_home() and the sqlite fallback
# must never touch the real ~/.llmtuner during tests.
_TMP_HOME = tempfile.mkdtemp(prefix="llmtuner-pytest-")
os.environ["LLMTUNER_HOME"] = _TMP_HOME
os.environ.setdefault("DATABASE_URL", "")

BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


@pytest.fixture()
def in_memory_db():
    """Fresh in-memory SQLite per test with all tables created."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from database import Base
    import models  # noqa: F401  (registers every table on Base.metadata)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(in_memory_db):
    """TestClient for a minimal app with just the auth router wired up.

    get_db is overridden to the in-memory session so auth tests exercise the
    real signup/login/me path without a server or the app database.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from database import get_db
    from routers import auth

    app = FastAPI()
    app.include_router(auth.router)

    def _override_db():
        yield in_memory_db

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as test_client:
        yield test_client
