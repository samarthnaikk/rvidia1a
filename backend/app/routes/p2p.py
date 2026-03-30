from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import Job
from app.models.p2p_signal import P2PSignal
from app.models.user import User
from app.routes.auth import get_current_user
from app.schemas.job import (
    JobCompletionRequest,
    JobUpdateStatusRequest,
    RegisterHostRequest,
    RegisterNodeRequest,
    SignalAnswerRequest,
    SignalCandidateRequest,
    SignalOfferRequest,
)

router = APIRouter()


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


def _is_owner(job: Job, user: User) -> bool:
    return job.user_id == user.id


def _is_requester(job: Job, user: User) -> bool:
    return job.access_requested_by is not None and job.access_requested_by == user.id


def _ensure_participant_access(job: Job, user: User) -> None:
    if _is_owner(job, user):
        return
    if _is_requester(job, user) and job.access_status == "accepted":
        return
    raise HTTPException(status_code=403, detail="Access not granted for this job")


def _marketplace_view(job: Job, current_user: User) -> dict:
    owner = _is_owner(job, current_user)
    requester = _is_requester(job, current_user)
    return {
        "job_id": job.id,
        "user_id": job.user_id,
        "repo_url": job.repo_url,
        "branch": job.branch,
        "status": job.status,
        "access_status": job.access_status,
        "created_at": job.created_at.isoformat(),
        "gpu_model": job.gpu_model,
        "gpu_vram": job.gpu_vram,
        "gpu_driver": job.gpu_driver,
        "can_request": (not owner) and job.access_status == "open",
        "can_accept": owner and job.access_status == "requested",
        "is_owner": owner,
        "is_requester": requester,
    }


# ── Marketplace endpoints ─────────────────────────────────────────────────────

@router.get("/hosts")
def list_hosts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return jobs that have a registered host, including GPU metadata."""
    jobs = (
        db.query(Job)
        .filter(Job.host_node_id.isnot(None))
        .order_by(Job.created_at.desc())
        .all()
    )
    return [
        {
            "job_id": j.id,
            "host_node_id": j.host_node_id,
            "status": j.status,
            "gpu_model": j.gpu_model,
            "gpu_vram": j.gpu_vram,
            "gpu_driver": j.gpu_driver,
            "access_status": j.access_status,
        }
        for j in jobs
    ]


@router.get("/jobs")
def list_marketplace_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return pending jobs with repo metadata for host browsing."""
    jobs = db.query(Job).order_by(Job.created_at.desc()).all()
    visible: list[dict] = []
    for job in jobs:
        owner = _is_owner(job, current_user)
        requester = _is_requester(job, current_user)
        if job.access_status == "open":
            visible.append(_marketplace_view(job, current_user))
            continue
        if owner or requester:
            visible.append(_marketplace_view(job, current_user))
    return visible


@router.get("/jobs/{job_id}/access")
def get_access_state(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    owner = _is_owner(job, current_user)
    requester = _is_requester(job, current_user)
    if not owner and not requester and job.access_status != "open":
        raise HTTPException(status_code=403, detail="Access state is private")
    return _marketplace_view(job, current_user)


@router.post("/jobs/{job_id}/request-access")
def request_access(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Renter signals intent to use a host's registered job slot."""
    job = _get_job(job_id, db)
    if _is_owner(job, current_user):
        raise HTTPException(status_code=400, detail="Job owner cannot request access to own job")
    if job.access_status != "open":
        raise HTTPException(status_code=409, detail=f"Job access is already '{job.access_status}'")
    job.access_status = "requested"
    job.access_requested_by = current_user.id
    db.commit()
    db.refresh(job)
    return {"job_id": job.id, "access_status": job.access_status, "requested_by": current_user.id}


@router.post("/jobs/{job_id}/accept-access")
def accept_access(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Host owner accepts the renter's request; CLI connect string is now active."""
    job = _get_job_for_user(job_id, current_user.id, db)
    if job.access_status != "requested":
        raise HTTPException(status_code=409, detail=f"No pending access request on job '{job_id}'")
    job.access_status = "accepted"
    job.status = "ready_for_transfer"
    db.commit()
    db.refresh(job)
    return {
        "job_id": job.id,
        "access_status": job.access_status,
        "status": job.status,
        "host_node_id": job.host_node_id,
        "receiver_node_id": job.receiver_node_id,
    }


# ── Node registration ─────────────────────────────────────────────────────────

@router.post("/jobs/{job_id}/register-host")
def register_host(
    job_id: str,
    payload: RegisterHostRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    if not _is_owner(job, current_user) and not _is_requester(job, current_user):
        raise HTTPException(status_code=403, detail="Only job participants can register as host")
    job.host_node_id = payload.node_id
    if payload.gpu_model is not None:
        job.gpu_model = payload.gpu_model
    if payload.gpu_vram is not None:
        job.gpu_vram = payload.gpu_vram
    if payload.gpu_driver is not None:
        job.gpu_driver = payload.gpu_driver
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
    if job.access_status != "accepted":
        raise HTTPException(status_code=409, detail="Access must be accepted before receiver can register")
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
    job = _get_job(job_id, db)
    _ensure_participant_access(job, current_user)
    return {
        "job_id": job.id,
        "host_node_id": job.host_node_id,
        "receiver_node_id": job.receiver_node_id,
        "ready": bool(job.host_node_id and job.receiver_node_id),
        "status": job.status,
    }


# ── Signaling ─────────────────────────────────────────────────────────────────

@router.post("/jobs/{job_id}/offer")
def push_offer(
    job_id: str,
    payload: SignalOfferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    _ensure_participant_access(job, current_user)
    db.add(P2PSignal(
        id=str(uuid4()),
        job_id=job_id,
        from_node_id=payload.from_node_id,
        to_node_id=payload.to_node_id,
        signal_type="offer",
        payload=payload.offer,
        delivered=False,
        created_at=datetime.utcnow(),
    ))
    db.commit()
    return {"queued": True}


@router.post("/jobs/{job_id}/answer")
def push_answer(
    job_id: str,
    payload: SignalAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    _ensure_participant_access(job, current_user)
    db.add(P2PSignal(
        id=str(uuid4()),
        job_id=job_id,
        from_node_id=payload.from_node_id,
        to_node_id=payload.to_node_id,
        signal_type="answer",
        payload=payload.answer,
        delivered=False,
        created_at=datetime.utcnow(),
    ))
    db.commit()
    return {"queued": True}


@router.post("/jobs/{job_id}/candidate")
def push_candidate(
    job_id: str,
    payload: SignalCandidateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    _ensure_participant_access(job, current_user)
    db.add(P2PSignal(
        id=str(uuid4()),
        job_id=job_id,
        from_node_id=payload.from_node_id,
        to_node_id=payload.to_node_id,
        signal_type="candidate",
        payload=payload.candidate,
        delivered=False,
        created_at=datetime.utcnow(),
    ))
    db.commit()
    return {"queued": True}


@router.get("/jobs/{job_id}/signals")
def pull_signals(
    job_id: str,
    node_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    _ensure_participant_access(job, current_user)

    rows = (
        db.query(P2PSignal)
        .filter(
            P2PSignal.job_id == job_id,
            P2PSignal.to_node_id == node_id,
            P2PSignal.delivered == False,  # noqa: E712
        )
        .order_by(P2PSignal.created_at.asc())
        .all()
    )

    now = datetime.utcnow()
    deliver: list[dict] = []
    for row in rows:
        deliver.append({
            "type": row.signal_type,
            "from_node_id": row.from_node_id,
            "to_node_id": row.to_node_id,
            "offer": row.payload,  # CLI always reads the "offer" field
        })
        row.delivered = True
        row.delivered_at = now

    if rows:
        db.commit()

    return {"signals": deliver}


@router.patch("/jobs/{job_id}/status")
def p2p_update_job_status(
    job_id: str,
    payload: JobUpdateStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    _ensure_participant_access(job, current_user)
    job.status = payload.status
    job.error_message = payload.error_message
    db.commit()
    db.refresh(job)
    return {
        "job_id": job.id,
        "status": job.status,
        "error_message": job.error_message,
    }


@router.post("/jobs/{job_id}/complete")
def p2p_complete_job(
    job_id: str,
    payload: JobCompletionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    _ensure_participant_access(job, current_user)
    job.status = "completed" if payload.success else "failed"
    job.artifact_name = payload.artifact_name
    job.artifact_path = payload.artifact_path
    job.error_message = payload.error_message
    db.commit()
    db.refresh(job)
    return {
        "job_id": job.id,
        "status": job.status,
        "artifact_name": job.artifact_name,
        "artifact_path": job.artifact_path,
        "error_message": job.error_message,
    }
