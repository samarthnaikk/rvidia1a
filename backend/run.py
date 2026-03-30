from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.database import Base, engine
from app.models import job, p2p_signal, user
from app.routes import auth, jobs, p2p


def ensure_jobs_schema() -> None:
    """Patch missing columns for existing DBs when no migration tool is present."""
    statements = [
        "ALTER TABLE IF EXISTS jobs ADD COLUMN IF NOT EXISTS repo_url VARCHAR",
        "ALTER TABLE IF EXISTS jobs ADD COLUMN IF NOT EXISTS branch VARCHAR NOT NULL DEFAULT 'main'",
        "ALTER TABLE IF EXISTS jobs ADD COLUMN IF NOT EXISTS gpu_model VARCHAR",
        "ALTER TABLE IF EXISTS jobs ADD COLUMN IF NOT EXISTS gpu_vram VARCHAR",
        "ALTER TABLE IF EXISTS jobs ADD COLUMN IF NOT EXISTS gpu_driver VARCHAR",
        "ALTER TABLE IF EXISTS jobs ADD COLUMN IF NOT EXISTS access_status VARCHAR NOT NULL DEFAULT 'open'",
        "ALTER TABLE IF EXISTS jobs ADD COLUMN IF NOT EXISTS access_requested_by INTEGER",
        "UPDATE jobs SET branch = 'main' WHERE branch IS NULL",
        "UPDATE jobs SET access_status = 'open' WHERE access_status IS NULL",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_p2p_signals_schema() -> None:
    """Bootstrap p2p_signals table for existing DBs that pre-date this model."""
    statements = [
        """
        CREATE TABLE IF NOT EXISTS p2p_signals (
            id VARCHAR PRIMARY KEY,
            job_id VARCHAR NOT NULL,
            from_node_id VARCHAR NOT NULL,
            to_node_id VARCHAR NOT NULL,
            signal_type VARCHAR NOT NULL,
            payload TEXT NOT NULL,
            delivered BOOLEAN NOT NULL DEFAULT FALSE,
            delivered_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_p2p_signals_job_id ON p2p_signals (job_id)",
        "CREATE INDEX IF NOT EXISTS ix_p2p_signals_to_node_id ON p2p_signals (to_node_id)",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


Base.metadata.create_all(bind=engine)
ensure_jobs_schema()
ensure_p2p_signals_schema()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
        "http://127.0.0.1",
        "http://157.180.74.2",
    ],
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
app.include_router(p2p.router, prefix="/p2p", tags=["P2P Coordination"])


@app.get("/")
def root():
    return {"message": "Hello from FastAPI"}
