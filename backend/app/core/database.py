import os
import re

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/appdb")


def _ensure_postgres_database_exists(database_url: str) -> None:
    """Create target Postgres database when persistent volumes predate current config."""
    try:
        url = make_url(database_url)
    except Exception:
        return

    if not url.drivername.startswith("postgresql"):
        return

    db_name = str(url.database or "").strip()
    if not db_name:
        return

    # Keep identifier handling safe for raw CREATE DATABASE statement.
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", db_name):
        return

    bootstrap_db = os.getenv("POSTGRES_BOOTSTRAP_DB", "postgres")
    if db_name == bootstrap_db:
        return

    bootstrap_url = url.set(database=bootstrap_db)
    bootstrap_engine = create_engine(
        bootstrap_url,
        pool_pre_ping=True,
        isolation_level="AUTOCOMMIT",
    )

    try:
        with bootstrap_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": db_name},
            ).scalar()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{db_name}"'))
    except Exception:
        # Keep bootstrap best-effort so local/dev imports do not fail when Postgres is unreachable.
        return
    finally:
        bootstrap_engine.dispose()


_ensure_postgres_database_exists(DATABASE_URL)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()