from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=False, default="")
    command: Mapped[str] = mapped_column(String, nullable=False, default="")
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued", index=True)

    # GitHub execution metadata
    repo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    branch: Mapped[str] = mapped_column(String, nullable=False, default="main")

    # Coordination metadata only; no file/log payloads are stored on server.
    host_node_id: Mapped[str | None] = mapped_column(String, nullable=True)
    receiver_node_id: Mapped[str | None] = mapped_column(String, nullable=True)
    latest_host_node_id: Mapped[str | None] = mapped_column(String, nullable=True)
    latest_receiver_node_id: Mapped[str | None] = mapped_column(String, nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    artifact_state: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")

    # GPU metadata reported by host on registration
    gpu_model: Mapped[str | None] = mapped_column(String, nullable=True)
    gpu_vram: Mapped[str | None] = mapped_column(String, nullable=True)
    gpu_driver: Mapped[str | None] = mapped_column(String, nullable=True)

    # Bilateral access consent
    access_status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    access_requested_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    artifact_name: Mapped[str | None] = mapped_column(String, nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
