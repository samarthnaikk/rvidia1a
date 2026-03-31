from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.core.database import Base, engine
from app.models import job, p2p_signal, user
from app.routes import auth, jobs, p2p


_JOB_COLUMN_MIGRATIONS: list[tuple[str, str]] = [
    ("repo_url", "VARCHAR"),
    ("branch", "VARCHAR NOT NULL DEFAULT 'main'"),
    ("gpu_model", "VARCHAR"),
    ("gpu_vram", "VARCHAR"),
    ("gpu_driver", "VARCHAR"),
    ("gpu_vram_mb", "INTEGER"),
    ("cpu_model", "VARCHAR"),
    ("cpu_physical_cores", "INTEGER"),
    ("cpu_logical_cores", "INTEGER"),
    ("cpu_max_clock_mhz", "INTEGER"),
    ("memory_total_mb", "INTEGER"),
    ("cpu_score", "DOUBLE PRECISION"),
    ("gpu_score", "DOUBLE PRECISION"),
    ("memory_score", "DOUBLE PRECISION"),
    ("machine_score", "DOUBLE PRECISION"),
    ("ranking_version", "VARCHAR"),
    ("access_status", "VARCHAR NOT NULL DEFAULT 'open'"),
    ("access_requested_by", "INTEGER"),
    ("latest_host_node_id", "VARCHAR"),
    ("latest_receiver_node_id", "VARCHAR"),
    ("session_version", "INTEGER NOT NULL DEFAULT 1"),
    ("artifact_state", "VARCHAR NOT NULL DEFAULT 'PENDING'"),
    ("host_heartbeat_at", "TIMESTAMP"),
    ("receiver_heartbeat_at", "TIMESTAMP"),
    ("failover_count", "INTEGER NOT NULL DEFAULT 0"),
    ("last_failover_reason", "TEXT"),
    ("checkpoint_phase", "VARCHAR"),
    ("checkpoint_data", "TEXT"),
    ("checkpoint_updated_at", "TIMESTAMP"),
]


def _table_columns(table_name: str) -> set[str]:
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def ensure_jobs_schema() -> None:
    """Patch missing columns for existing DBs when no migration tool is present."""
    existing_columns = _table_columns("jobs")
    if not existing_columns:
        return

    with engine.begin() as connection:
        for column_name, ddl in _JOB_COLUMN_MIGRATIONS:
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE jobs ADD COLUMN {column_name} {ddl}"))

        connection.execute(text("UPDATE jobs SET branch = 'main' WHERE branch IS NULL"))
        connection.execute(text("UPDATE jobs SET access_status = 'open' WHERE access_status IS NULL"))
        connection.execute(text("UPDATE jobs SET session_version = 1 WHERE session_version IS NULL"))
        connection.execute(text("UPDATE jobs SET failover_count = 0 WHERE failover_count IS NULL"))
        connection.execute(text("UPDATE jobs SET artifact_state = 'PENDING' WHERE artifact_state IS NULL"))


def ensure_p2p_signals_schema() -> None:
    """Ensure p2p_signals indexes exist for older databases."""
    inspector = inspect(engine)
    if not inspector.has_table("p2p_signals"):
        return

    existing_indexes = {index["name"] for index in inspector.get_indexes("p2p_signals")}

    with engine.begin() as connection:
        if "ix_p2p_signals_job_id" not in existing_indexes:
            connection.execute(text("CREATE INDEX ix_p2p_signals_job_id ON p2p_signals (job_id)"))
        if "ix_p2p_signals_to_node_id" not in existing_indexes:
            connection.execute(text("CREATE INDEX ix_p2p_signals_to_node_id ON p2p_signals (to_node_id)"))


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
