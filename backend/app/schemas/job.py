from datetime import datetime
from typing import Any

from pydantic import BaseModel


class JobCreateRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    # Legacy fields kept for backwards compatibility; unused in Docker mode.
    filename: str = ""
    command: str = ""


class JobUpdateStatusRequest(BaseModel):
    status: str
    error_message: str | None = None


class JobCompletionRequest(BaseModel):
    success: bool
    artifact_name: str | None = None
    artifact_path: str | None = None
    error_message: str | None = None


class JobResponse(BaseModel):
    id: str
    user_id: int
    filename: str
    command: str
    repo_url: str | None
    branch: str
    status: str
    host_node_id: str | None
    receiver_node_id: str | None
    latest_host_node_id: str | None
    latest_receiver_node_id: str | None
    session_version: int
    artifact_state: str
    gpu_model: str | None
    gpu_vram: str | None
    gpu_driver: str | None
    gpu_vram_mb: int | None
    cpu_model: str | None
    cpu_physical_cores: int | None
    cpu_logical_cores: int | None
    cpu_max_clock_mhz: int | None
    memory_total_mb: int | None
    cpu_score: float | None
    gpu_score: float | None
    memory_score: float | None
    machine_score: float | None
    ranking_version: str | None
    access_status: str
    access_requested_by: int | None
    artifact_name: str | None
    artifact_path: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RegisterNodeRequest(BaseModel):
    node_id: str


class RegisterHostRequest(BaseModel):
    node_id: str
    gpu_model: str | None = None
    gpu_vram: str | None = None
    gpu_driver: str | None = None
    gpu_vram_mb: int | None = None
    cpu_model: str | None = None
    cpu_physical_cores: int | None = None
    cpu_logical_cores: int | None = None
    cpu_max_clock_mhz: int | None = None
    memory_total_mb: int | None = None
    cpu_score: float | None = None
    gpu_score: float | None = None
    memory_score: float | None = None
    machine_score: float | None = None
    ranking_version: str | None = None


class AccessRequestPayload(BaseModel):
    hardware_metadata: dict[str, Any] | None = None


class AcceptAccessRequest(BaseModel):
    requester_user_id: int | None = None


class SignalOfferRequest(BaseModel):
    from_node_id: str
    to_node_id: str
    offer: str


class SignalAnswerRequest(BaseModel):
    from_node_id: str
    to_node_id: str
    answer: str


class SignalCandidateRequest(BaseModel):
    from_node_id: str
    to_node_id: str
    candidate: str


class ArtifactStateUpdateRequest(BaseModel):
    artifact_state: str
