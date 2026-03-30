"""Shared pytest fixtures for backend tests."""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import job, p2p_signal, user  # noqa: F401 — register models


@pytest.fixture(scope="function")
def db_session():
    """In-memory SQLite session for unit tests (no Postgres needed)."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
