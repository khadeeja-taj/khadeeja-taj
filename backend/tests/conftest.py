"""Pytest fixtures: an isolated SQLite database and a TestClient per test."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.seed import seed_programs


@pytest.fixture()
def db_session(tmp_path):
    """A fresh file-backed SQLite DB, seeded with the program pack."""
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )

    # Import models so metadata is populated, then create schema.
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    seed_programs(session)
    try:
        yield TestingSessionLocal
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    """TestClient wired to the isolated test database (no lifespan seeding)."""
    TestingSessionLocal = db_session

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Instantiate without a context manager so the app lifespan (which would
    # create/seed the default database) does not run — the fixture already
    # created and seeded an isolated test database above.
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()
