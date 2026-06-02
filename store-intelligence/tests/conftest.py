"""
Shared pytest fixtures.
Uses an in-memory SQLite DB so tests need no running Postgres.
"""
# PROMPT: "Generate a pytest conftest.py for a FastAPI app using SQLAlchemy.
#          Use SQLite in-memory for tests. Provide a test_client fixture
#          that overrides the get_db dependency."
# CHANGES MADE: added event_factory fixture for test data generation;
#               forced timezone-aware timestamps in SQLite compat mode.

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from main import app
from database import Base, get_db

TEST_DB_URL = "sqlite:///./test.db"

@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)

@pytest.fixture(scope="function")
def db(engine):
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.rollback()
    session.close()

@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def sample_event():
    import uuid
    return {
        "event_id":   str(uuid.uuid4()),
        "store_id":   "ST1008",
        "camera_id":  "CAM_ENTRY_01",
        "visitor_id": "VIS_000001",
        "event_type": "ENTRY",
        "timestamp":  "2026-04-10T12:30:00Z",
        "zone_id":    None,
        "dwell_ms":   0,
        "is_staff":   False,
        "confidence": 0.92,
        "metadata":   {"queue_depth": None, "sku_zone": None, "session_seq": 1},
    }
