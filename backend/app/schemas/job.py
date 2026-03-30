from datetime import datetime

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
