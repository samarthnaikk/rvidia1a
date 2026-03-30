from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import Job
from app.models.user import User
from app.routes.auth import get_current_user
from app.schemas.job import (
    RegisterNodeRequest,
    SignalAnswerRequest,
    SignalCandidateRequest,
    SignalOfferRequest,
)

router = APIRouter()


# In-memory signaling queue for MVP coordination only.
_SIGNALS: dict[str, list[dict]] = {}


def _get_job_for_user(job_id: str, user_id: int, db: Session) -> Job:
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _get_job(job_id: str, db: Session) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _queue_signal(job_id: str, signal: dict) -> None:
    if job_id not in _SIGNALS:
        _SIGNALS[job_id] = []
    _SIGNALS[job_id].append(signal)


@router.post("/jobs/{job_id}/register-host")
def register_host(
    job_id: str,
    payload: RegisterNodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    job.host_node_id = payload.node_id
    if job.status == "queued":
        job.status = "awaiting_receiver"
    db.commit()
    db.refresh(job)
    return {"job_id": job.id, "host_node_id": job.host_node_id, "status": job.status}


@router.post("/jobs/{job_id}/register-receiver")
def register_receiver(
    job_id: str,
    payload: RegisterNodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job_for_user(job_id, current_user.id, db)
    job.receiver_node_id = payload.node_id
    if job.host_node_id:
        job.status = "ready_for_transfer"
    db.commit()
    db.refresh(job)
    return {
        "job_id": job.id,
        "receiver_node_id": job.receiver_node_id,
        "host_node_id": job.host_node_id,
        "status": job.status,
    }


@router.get("/jobs/{job_id}/peers")
def get_job_peers(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job_for_user(job_id, current_user.id, db)
    return {
        "job_id": job.id,
        "host_node_id": job.host_node_id,
        "receiver_node_id": job.receiver_node_id,
        "ready": bool(job.host_node_id and job.receiver_node_id),
        "status": job.status,
    }


@router.post("/jobs/{job_id}/offer")
def push_offer(
    job_id: str,
    payload: SignalOfferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_job(job_id, db)
    _queue_signal(
        job_id,
        {
            "type": "offer",
            "from_node_id": payload.from_node_id,
            "to_node_id": payload.to_node_id,
            "offer": payload.offer,
        },
    )
    return {"queued": True}


@router.post("/jobs/{job_id}/answer")
def push_answer(
    job_id: str,
    payload: SignalAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_job(job_id, db)
    _queue_signal(
        job_id,
        {
            "type": "answer",
            "from_node_id": payload.from_node_id,
            "to_node_id": payload.to_node_id,
            "answer": payload.answer,
        },
    )
    return {"queued": True}


@router.post("/jobs/{job_id}/candidate")
def push_candidate(
    job_id: str,
    payload: SignalCandidateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_job(job_id, db)
    _queue_signal(
        job_id,
        {
            "type": "candidate",
            "from_node_id": payload.from_node_id,
            "to_node_id": payload.to_node_id,
            "candidate": payload.candidate,
        },
    )
    return {"queued": True}


@router.get("/jobs/{job_id}/signals")
def pull_signals(
    job_id: str,
    node_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_job(job_id, db)
    queue = _SIGNALS.get(job_id, [])
    deliver: list[dict] = []
    remaining: list[dict] = []
    for item in queue:
        if item.get("to_node_id") == node_id:
            deliver.append(item)
        else:
            remaining.append(item)
    _SIGNALS[job_id] = remaining
    return {"signals": deliver}
