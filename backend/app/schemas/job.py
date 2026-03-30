from datetime import datetime

from pydantic import BaseModel


class JobCreateRequest(BaseModel):
    filename: str
    command: str


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
    status: str
    host_node_id: str | None
    receiver_node_id: str | None
    artifact_name: str | None
    artifact_path: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RegisterNodeRequest(BaseModel):
    node_id: str


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
