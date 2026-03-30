import json
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import Job
from app.models.p2p_access_request import P2PAccessRequest
from app.models.p2p_signal import P2PSignal
from app.models.user import User
from app.routes.auth import get_current_user
from app.schemas.job import (
    AcceptAccessRequest,
    AccessRequestPayload,
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


def _request_row_for_user(job_id: str, user_id: int, db: Session) -> P2PAccessRequest | None:
    return (
        db.query(P2PAccessRequest)
        .filter(P2PAccessRequest.job_id == job_id, P2PAccessRequest.requester_user_id == user_id)
        .first()
    )


def _is_accepted_requester(job_id: str, user_id: int, db: Session) -> bool:
    row = _request_row_for_user(job_id, user_id, db)
    return row is not None and row.status == "accepted"


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _parse_hardware_metadata(payload: AccessRequestPayload) -> dict:
    raw = payload.hardware_metadata or {}
    if not isinstance(raw, dict):
        raw = {}

    gpu_vram_mb = _safe_int(raw.get("gpu_vram_mb"))
    if gpu_vram_mb is None:
        gpu_vram_raw = raw.get("gpu_vram")
        if isinstance(gpu_vram_raw, str):
            digits = "".join(ch for ch in gpu_vram_raw if ch.isdigit())
            if digits:
                gpu_vram_mb = _safe_int(digits)

    ram_mb = _safe_int(raw.get("ram_mb"))
    if ram_mb is None:
        ram_mb = _safe_int(raw.get("memory_total_mb"))

    total_score = _safe_float(raw.get("total_score"))
    if total_score is None:
        total_score = _safe_float(raw.get("machine_score"))

    return {
        "cpu_model": str(raw.get("cpu_model") or raw.get("cpu_name") or "") or None,
        "gpu_model": str(raw.get("gpu_model") or raw.get("gpu_name") or "") or None,
        "gpu_vram_mb": gpu_vram_mb,
        "ram_mb": ram_mb,
        "total_score": total_score,
    }


def _sync_job_access_state(job: Job, db: Session) -> None:
    requested_rows = (
        db.query(P2PAccessRequest)
        .filter(P2PAccessRequest.job_id == job.id, P2PAccessRequest.status == "requested")
        .order_by(P2PAccessRequest.created_at.asc())
        .all()
    )
    accepted_count = (
        db.query(P2PAccessRequest)
        .filter(P2PAccessRequest.job_id == job.id, P2PAccessRequest.status == "accepted")
        .count()
    )

    if accepted_count > 0:
        job.access_status = "accepted"
        job.access_requested_by = None
        return
    if requested_rows:
        job.access_status = "requested"
        job.access_requested_by = requested_rows[0].requester_user_id
        return
    job.access_status = "open"
    job.access_requested_by = None


def _effective_access_status(job: Job, current_user: User, db: Session) -> str:
    if _is_owner(job, current_user):
        return job.access_status
    row = _request_row_for_user(job.id, current_user.id, db)
    if row is not None:
        return row.status
    return "open"


def _ensure_participant_access(job: Job, user: User, db: Session) -> None:
    if _is_owner(job, user):
        return
    if _is_accepted_requester(job.id, user.id, db):
        return
    raise HTTPException(status_code=403, detail="Access not granted for this job")


def _accepted_hosts_for_job(job_id: str, db: Session) -> list[dict]:
    rows = (
        db.query(P2PAccessRequest)
        .filter(P2PAccessRequest.job_id == job_id, P2PAccessRequest.status == "accepted")
        .order_by(
            case((P2PAccessRequest.total_score.is_(None), 1), else_=0).asc(),
            P2PAccessRequest.total_score.desc(),
            P2PAccessRequest.created_at.asc(),
        )
        .all()
    )

    accepted_hosts: list[dict] = []
    for index, row in enumerate(rows, start=1):
        hardware = {}
        if row.hardware_metadata:
            try:
                decoded = json.loads(row.hardware_metadata)
                if isinstance(decoded, dict):
                    hardware = decoded
            except json.JSONDecodeError:
                hardware = {}
        accepted_hosts.append(
            {
                "rank": index,
                "request_id": row.id,
                "requester_user_id": row.requester_user_id,
                "status": row.status,
                "cpu_model": row.cpu_model,
                "gpu_model": row.gpu_model,
                "gpu_vram_mb": row.gpu_vram_mb,
                "ram_mb": row.ram_mb,
                "total_score": row.total_score,
                "hardware_metadata": hardware,
                "created_at": row.created_at.isoformat(),
            }
        )
    return accepted_hosts


def _marketplace_view(job: Job, current_user: User, db: Session) -> dict:
    owner = _is_owner(job, current_user)
    my_request = _request_row_for_user(job.id, current_user.id, db)
    requested_count = (
        db.query(P2PAccessRequest)
        .filter(P2PAccessRequest.job_id == job.id, P2PAccessRequest.status == "requested")
        .count()
    )
    accepted_count = (
        db.query(P2PAccessRequest)
        .filter(P2PAccessRequest.job_id == job.id, P2PAccessRequest.status == "accepted")
        .count()
    )
    return {
        "job_id": job.id,
        "user_id": job.user_id,
        "repo_url": job.repo_url,
        "branch": job.branch,
        "status": job.status,
        "access_status": _effective_access_status(job, current_user, db),
        "created_at": job.created_at.isoformat(),
        "gpu_model": job.gpu_model,
        "gpu_vram": job.gpu_vram,
        "gpu_driver": job.gpu_driver,
        "can_request": (not owner) and (my_request is None or my_request.status not in ("requested", "accepted")),
        "can_accept": owner and requested_count > 0,
        "is_owner": owner,
        "is_requester": my_request is not None,
        "my_request_status": my_request.status if my_request else None,
        "requested_count": requested_count,
        "accepted_count": accepted_count,
    }


@router.get("/hosts")
def list_hosts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    jobs = db.query(Job).order_by(Job.created_at.desc()).all()
    visible: list[dict] = []
    for job in jobs:
        owner = _is_owner(job, current_user)
        my_request = _request_row_for_user(job.id, current_user.id, db)
        if job.access_status == "open":
            visible.append(_marketplace_view(job, current_user, db))
            continue
        if owner or my_request is not None:
            visible.append(_marketplace_view(job, current_user, db))
    return visible


@router.get("/jobs/{job_id}/access")
def get_access_state(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    owner = _is_owner(job, current_user)
    my_request = _request_row_for_user(job.id, current_user.id, db)
    if not owner and my_request is None and job.access_status != "open":
        raise HTTPException(status_code=403, detail="Access state is private")
    return _marketplace_view(job, current_user, db)


@router.post("/jobs/{job_id}/request-access")
def request_access(
    job_id: str,
    payload: AccessRequestPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    if _is_owner(job, current_user):
        raise HTTPException(status_code=400, detail="Job owner cannot request access to own job")

    existing = _request_row_for_user(job.id, current_user.id, db)
    if existing is not None and existing.status == "accepted":
        raise HTTPException(status_code=409, detail="Access already accepted for this requester")

    parsed = _parse_hardware_metadata(payload)
    serialized_metadata = json.dumps(payload.hardware_metadata or {})
    if existing is None:
        existing = P2PAccessRequest(
            job_id=job.id,
            requester_user_id=current_user.id,
            status="requested",
        )
        db.add(existing)
    else:
        existing.status = "requested"

    existing.hardware_metadata = serialized_metadata
    existing.cpu_model = parsed["cpu_model"]
    existing.gpu_model = parsed["gpu_model"]
    existing.gpu_vram_mb = parsed["gpu_vram_mb"]
    existing.ram_mb = parsed["ram_mb"]
    existing.total_score = parsed["total_score"]

    _sync_job_access_state(job, db)
    db.commit()
    db.refresh(job)
    db.refresh(existing)
    return {
        "job_id": job.id,
        "access_status": _effective_access_status(job, current_user, db),
        "requested_by": current_user.id,
        "request_id": existing.id,
        "total_score": existing.total_score,
    }


@router.post("/jobs/{job_id}/accept-access")
def accept_access(
    job_id: str,
    payload: AcceptAccessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job_for_user(job_id, current_user.id, db)

    selected: P2PAccessRequest | None = None
    if payload.requester_user_id is not None:
        selected = (
            db.query(P2PAccessRequest)
            .filter(
                P2PAccessRequest.job_id == job.id,
                P2PAccessRequest.requester_user_id == payload.requester_user_id,
            )
            .first()
        )
    else:
        selected = (
            db.query(P2PAccessRequest)
            .filter(P2PAccessRequest.job_id == job.id, P2PAccessRequest.status == "requested")
            .order_by(P2PAccessRequest.created_at.asc())
            .first()
        )

    if selected is None:
        raise HTTPException(status_code=409, detail=f"No pending access request on job '{job_id}'")

    selected.status = "accepted"
    job.status = "ready_for_transfer"
    _sync_job_access_state(job, db)
    db.commit()
    db.refresh(job)

    return {
        "job_id": job.id,
        "accepted_requester_user_id": selected.requester_user_id,
        "access_status": job.access_status,
        "status": job.status,
        "accepted_hosts": _accepted_hosts_for_job(job.id, db),
    }


@router.get("/jobs/{job_id}/requests")
def list_access_requests(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    if not _is_owner(job, current_user):
        raise HTTPException(status_code=403, detail="Only job owner can view requests")

    rows = (
        db.query(P2PAccessRequest)
        .filter(P2PAccessRequest.job_id == job.id)
        .order_by(
            case((P2PAccessRequest.status == "requested", 0), else_=1).asc(),
            case((P2PAccessRequest.total_score.is_(None), 1), else_=0).asc(),
            P2PAccessRequest.total_score.desc(),
            P2PAccessRequest.created_at.asc(),
        )
        .all()
    )

    requests = []
    for row in rows:
        metadata: dict = {}
        if row.hardware_metadata:
            try:
                decoded = json.loads(row.hardware_metadata)
                if isinstance(decoded, dict):
                    metadata = decoded
            except json.JSONDecodeError:
                metadata = {}
        requests.append(
            {
                "request_id": row.id,
                "requester_user_id": row.requester_user_id,
                "status": row.status,
                "cpu_model": row.cpu_model,
                "gpu_model": row.gpu_model,
                "gpu_vram_mb": row.gpu_vram_mb,
                "ram_mb": row.ram_mb,
                "total_score": row.total_score,
                "hardware_metadata": metadata,
                "created_at": row.created_at.isoformat(),
            }
        )
    return {"job_id": job.id, "requests": requests}


@router.get("/jobs/{job_id}/accepted-hosts")
def list_accepted_hosts(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    if not _is_owner(job, current_user):
        raise HTTPException(status_code=403, detail="Only job owner can view accepted hosts")
    return {"job_id": job.id, "accepted_hosts": _accepted_hosts_for_job(job.id, db)}


@router.post("/jobs/{job_id}/register-host")
def register_host(
    job_id: str,
    payload: RegisterHostRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    if not _is_owner(job, current_user) and not _is_accepted_requester(job.id, current_user.id, db):
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
    _ensure_participant_access(job, current_user, db)
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
    job = _get_job(job_id, db)
    _ensure_participant_access(job, current_user, db)
    db.add(
        P2PSignal(
            id=str(uuid4()),
            job_id=job_id,
            from_node_id=payload.from_node_id,
            to_node_id=payload.to_node_id,
            signal_type="offer",
            payload=payload.offer,
            delivered=False,
            created_at=datetime.utcnow(),
        )
    )
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
    _ensure_participant_access(job, current_user, db)
    db.add(
        P2PSignal(
            id=str(uuid4()),
            job_id=job_id,
            from_node_id=payload.from_node_id,
            to_node_id=payload.to_node_id,
            signal_type="answer",
            payload=payload.answer,
            delivered=False,
            created_at=datetime.utcnow(),
        )
    )
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
    _ensure_participant_access(job, current_user, db)
    db.add(
        P2PSignal(
            id=str(uuid4()),
            job_id=job_id,
            from_node_id=payload.from_node_id,
            to_node_id=payload.to_node_id,
            signal_type="candidate",
            payload=payload.candidate,
            delivered=False,
            created_at=datetime.utcnow(),
        )
    )
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
    _ensure_participant_access(job, current_user, db)

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
        deliver.append(
            {
                "type": row.signal_type,
                "from_node_id": row.from_node_id,
                "to_node_id": row.to_node_id,
                "offer": row.payload,
            }
        )
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
    _ensure_participant_access(job, current_user, db)
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
    _ensure_participant_access(job, current_user, db)
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
