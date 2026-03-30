import json
from collections import defaultdict
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import Job
from app.models.p2p_signal import P2PSignal
from app.models.user import User
from app.routes.auth import get_current_user
from app.schemas.job import (
    AcceptAccessRequest,
    AccessRequestPayload,
    ArtifactStateUpdateRequest,
    CheckpointUpdateRequest,
    HeartbeatRequest,
    JobCompletionRequest,
    JobUpdateStatusRequest,
    RegisterHostRequest,
    RegisterNodeRequest,
    SignalAnswerRequest,
    SignalCandidateRequest,
    SignalOfferRequest,
)

router = APIRouter()
_HEARTBEAT_TIMEOUT_SECONDS = 45


def _as_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _as_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


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


def _bump_session(job: Job) -> None:
    current = int(job.session_version or 0)
    job.session_version = current + 1


def _is_stale(heartbeat: datetime | None, now: datetime) -> bool:
    if heartbeat is None:
        return False
    return (now - heartbeat) > timedelta(seconds=_HEARTBEAT_TIMEOUT_SECONDS)


def _apply_stale_failover(job: Job, now: datetime) -> bool:
    # Do not mutate terminal jobs; heartbeats naturally stop after completion.
    if job.status in {"completed", "failed"}:
        return False

    changed = False
    host_stale = bool(job.host_node_id) and _is_stale(job.host_heartbeat_at, now)
    receiver_stale = bool(job.receiver_node_id) and _is_stale(job.receiver_heartbeat_at, now)

    if host_stale:
        job.host_node_id = None
        job.host_heartbeat_at = None
        job.failover_count = int(job.failover_count or 0) + 1
        job.last_failover_reason = "host_heartbeat_timeout"
        job.checkpoint_phase = "system:failover_host_timeout"
        job.checkpoint_data = json.dumps({
            "reason": "host_heartbeat_timeout",
            "recorded_at": now.isoformat(),
        })
        job.checkpoint_updated_at = now
        job.status = "queued"
        job.artifact_state = "PENDING"
        job.error_message = "Host became unreachable; job was re-queued for failover"
        _bump_session(job)
        changed = True

    if receiver_stale:
        job.receiver_node_id = None
        job.receiver_heartbeat_at = None
        if job.status in {"ready_for_transfer", "transferring"}:
            job.status = "awaiting_receiver"
        job.failover_count = int(job.failover_count or 0) + 1
        job.last_failover_reason = "receiver_heartbeat_timeout"
        job.checkpoint_phase = "system:failover_receiver_timeout"
        job.checkpoint_data = json.dumps({
            "reason": "receiver_heartbeat_timeout",
            "recorded_at": now.isoformat(),
        })
        job.checkpoint_updated_at = now
        _bump_session(job)
        changed = True

    return changed


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
        "gpu_vram_mb": job.gpu_vram_mb,
        "cpu_model": job.cpu_model,
        "cpu_physical_cores": job.cpu_physical_cores,
        "cpu_logical_cores": job.cpu_logical_cores,
        "cpu_max_clock_mhz": job.cpu_max_clock_mhz,
        "memory_total_mb": job.memory_total_mb,
        "cpu_score": job.cpu_score,
        "gpu_score": job.gpu_score,
        "memory_score": job.memory_score,
        "machine_score": job.machine_score,
        "ranking_version": job.ranking_version,
        "session_version": job.session_version,
        "artifact_state": job.artifact_state,
        "host_heartbeat_at": job.host_heartbeat_at.isoformat() if job.host_heartbeat_at else None,
        "receiver_heartbeat_at": job.receiver_heartbeat_at.isoformat() if job.receiver_heartbeat_at else None,
        "failover_count": job.failover_count,
        "last_failover_reason": job.last_failover_reason,
        "checkpoint_phase": job.checkpoint_phase,
        "checkpoint_data": job.checkpoint_data,
        "checkpoint_updated_at": job.checkpoint_updated_at.isoformat() if job.checkpoint_updated_at else None,
        "latest_host_node_id": job.latest_host_node_id,
        "latest_receiver_node_id": job.latest_receiver_node_id,
        "can_request": (not owner) and job.access_status == "open",
        "can_accept": owner and job.access_status == "requested",
        "is_owner": owner,
        "is_requester": requester,
    }


def _heartbeat_age_seconds(heartbeat: datetime | None, now: datetime) -> int | None:
    if heartbeat is None:
        return None
    return max(0, int((now - heartbeat).total_seconds()))


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
    now = datetime.utcnow()
    changed = False
    for job in jobs:
        changed = _apply_stale_failover(job, now) or changed
    if changed:
        db.commit()
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
            "gpu_vram_mb": j.gpu_vram_mb,
            "cpu_model": j.cpu_model,
            "cpu_physical_cores": j.cpu_physical_cores,
            "cpu_logical_cores": j.cpu_logical_cores,
            "cpu_max_clock_mhz": j.cpu_max_clock_mhz,
            "memory_total_mb": j.memory_total_mb,
            "cpu_score": j.cpu_score,
            "gpu_score": j.gpu_score,
            "memory_score": j.memory_score,
            "machine_score": j.machine_score,
            "ranking_version": j.ranking_version,
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
    now = datetime.utcnow()
    changed = False
    for job in jobs:
        changed = _apply_stale_failover(job, now) or changed
    if changed:
        db.commit()
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
    if _apply_stale_failover(job, datetime.utcnow()):
        db.commit()
        db.refresh(job)
    owner = _is_owner(job, current_user)
    requester = _is_requester(job, current_user)
    if not owner and not requester and job.access_status != "open":
        raise HTTPException(status_code=403, detail="Access state is private")
    return _marketplace_view(job, current_user)


@router.post("/jobs/{job_id}/request-access")
def request_access(
    job_id: str,
    payload: AccessRequestPayload,
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
    job.artifact_state = "PENDING"

    metadata = payload.hardware_metadata or {}
    if isinstance(metadata, dict):
        # Compatibility path: allow browser-side specs to populate job metadata
        # before host registration, so older UIs can still show machine details.
        if metadata.get("cpu_model") and not job.cpu_model:
            job.cpu_model = str(metadata.get("cpu_model"))
        cpu_physical_cores = _as_int(metadata.get("cpu_physical_cores"))
        if cpu_physical_cores is not None and not job.cpu_physical_cores:
            job.cpu_physical_cores = cpu_physical_cores
        cpu_logical_cores = _as_int(metadata.get("cpu_logical_cores"))
        if cpu_logical_cores is not None and not job.cpu_logical_cores:
            job.cpu_logical_cores = cpu_logical_cores
        cpu_max_clock_mhz = _as_int(metadata.get("cpu_max_clock_mhz"))
        if cpu_max_clock_mhz is not None and not job.cpu_max_clock_mhz:
            job.cpu_max_clock_mhz = cpu_max_clock_mhz
        if metadata.get("gpu_model") and not job.gpu_model:
            job.gpu_model = str(metadata.get("gpu_model"))
        if metadata.get("gpu_vram") and not job.gpu_vram:
            job.gpu_vram = str(metadata.get("gpu_vram"))
        if metadata.get("gpu_driver") and not job.gpu_driver:
            job.gpu_driver = str(metadata.get("gpu_driver"))
        gpu_vram_mb = _as_int(metadata.get("gpu_vram_mb"))
        if gpu_vram_mb is not None and not job.gpu_vram_mb:
            job.gpu_vram_mb = gpu_vram_mb
        memory_total_mb = _as_int(metadata.get("memory_total_mb"))
        if memory_total_mb is not None and not job.memory_total_mb:
            job.memory_total_mb = memory_total_mb
        cpu_score = _as_float(metadata.get("cpu_score"))
        if cpu_score is not None and job.cpu_score is None:
            job.cpu_score = cpu_score
        gpu_score = _as_float(metadata.get("gpu_score"))
        if gpu_score is not None and job.gpu_score is None:
            job.gpu_score = gpu_score
        memory_score = _as_float(metadata.get("memory_score"))
        if memory_score is not None and job.memory_score is None:
            job.memory_score = memory_score
        machine_score = _as_float(metadata.get("machine_score"))
        if machine_score is not None and job.machine_score is None:
            job.machine_score = machine_score
        if metadata.get("ranking_version") and not job.ranking_version:
            job.ranking_version = str(metadata.get("ranking_version"))

    db.commit()
    db.refresh(job)
    return {"job_id": job.id, "access_status": job.access_status, "requested_by": current_user.id}


@router.post("/jobs/{job_id}/accept-access")
def accept_access(
    job_id: str,
    payload: AcceptAccessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Host owner accepts the renter's request; CLI connect string is now active."""
    job = _get_job_for_user(job_id, current_user.id, db)
    if job.access_status != "requested":
        raise HTTPException(status_code=409, detail=f"No pending access request on job '{job_id}'")
    job.access_status = "accepted"
    job.status = "ready_for_transfer"
    job.artifact_state = "PENDING"
    db.commit()
    db.refresh(job)
    return {
        "job_id": job.id,
        "access_status": job.access_status,
        "status": job.status,
        "host_node_id": job.host_node_id,
        "receiver_node_id": job.receiver_node_id,
    }


@router.get("/jobs/{job_id}/requests")
def list_job_requests(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Backward-compatible endpoint for older frontend builds."""
    job = _get_job(job_id, db)
    if not _is_owner(job, current_user):
        raise HTTPException(status_code=403, detail="Only owner can view job requests")

    requests: list[dict[str, object]] = []
    if job.access_requested_by is not None and job.access_status in {"requested", "accepted"}:
        requests.append(
            {
                "request_id": f"job-{job.id}-req-{job.access_requested_by}",
                "requester_user_id": job.access_requested_by,
                "status": job.access_status,
                "cpu_model": job.cpu_model,
                "gpu_model": job.gpu_model,
                "gpu_vram_mb": job.gpu_vram_mb,
                "ram_mb": job.memory_total_mb,
                "total_score": job.machine_score,
                "hardware_metadata": {
                    "cpu_model": job.cpu_model,
                    "gpu_model": job.gpu_model,
                    "gpu_vram_mb": job.gpu_vram_mb,
                    "memory_total_mb": job.memory_total_mb,
                    "machine_score": job.machine_score,
                },
            }
        )
    return {"job_id": job.id, "requests": requests}


@router.get("/jobs/{job_id}/accepted-hosts")
def list_accepted_hosts(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Backward-compatible endpoint for older frontend builds."""
    job = _get_job(job_id, db)
    if not _is_owner(job, current_user):
        raise HTTPException(status_code=403, detail="Only owner can view accepted hosts")

    hosts: list[dict[str, object]] = []
    if job.access_status == "accepted" and job.host_node_id:
        hosts.append(
            {
                "host_node_id": job.host_node_id,
                "status": job.status,
                "gpu_model": job.gpu_model,
                "gpu_vram": job.gpu_vram,
                "gpu_driver": job.gpu_driver,
                "cpu_model": job.cpu_model,
                "memory_total_mb": job.memory_total_mb,
                "machine_score": job.machine_score,
            }
        )
    return {"job_id": job.id, "accepted_hosts": hosts}


@router.get("/telemetry")
def get_telemetry(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    del current_user
    jobs = db.query(Job).all()
    now = datetime.utcnow()

    status_counts: dict[str, int] = defaultdict(int)
    active_hosts = 0
    active_receivers = 0
    pending_failovers = 0
    delivered_artifacts = 0
    machine_scores: list[float] = []

    for job in jobs:
        status = str(job.status or "unknown")
        status_counts[status] += 1
        if job.artifact_state == "DELIVERED":
            delivered_artifacts += 1
        if job.machine_score is not None:
            machine_scores.append(float(job.machine_score))
        if job.last_failover_reason and status not in {"completed", "failed"}:
            pending_failovers += 1

        if job.host_node_id and not _is_stale(job.host_heartbeat_at, now):
            active_hosts += 1
        if job.receiver_node_id and not _is_stale(job.receiver_heartbeat_at, now):
            active_receivers += 1

    avg_machine_score = round(sum(machine_scores) / len(machine_scores), 2) if machine_scores else None

    return {
        "timestamp": now.isoformat(),
        "jobs_total": len(jobs),
        "active_hosts": active_hosts,
        "active_receivers": active_receivers,
        "status_counts": dict(status_counts),
        "pending_failovers": pending_failovers,
        "delivered_artifacts": delivered_artifacts,
        "average_machine_score": avg_machine_score,
    }


@router.get("/contributors/summary")
def get_contributor_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    del current_user
    now = datetime.utcnow()
    jobs = (
        db.query(Job)
        .filter((Job.latest_host_node_id.isnot(None)) | (Job.host_node_id.isnot(None)))
        .order_by(Job.created_at.desc())
        .all()
    )

    by_node: dict[str, dict] = {}
    for job in jobs:
        node_id = str(job.latest_host_node_id or job.host_node_id or "").strip()
        if not node_id:
            continue

        row = by_node.get(node_id)
        if row is None:
            row = {
                "node_id": node_id,
                "jobs_total": 0,
                "completed_jobs": 0,
                "failed_jobs": 0,
                "in_progress_jobs": 0,
                "first_seen_at": job.created_at.isoformat() if job.created_at else None,
                "last_seen_at": job.updated_at.isoformat() if job.updated_at else None,
                "last_status": job.status,
                "gpu_model": job.gpu_model,
                "avg_machine_score": None,
                "active_now": False,
            }
            row["_score_sum"] = 0.0
            row["_score_count"] = 0
            by_node[node_id] = row

        row["jobs_total"] += 1
        status = str(job.status or "")
        if status == "completed":
            row["completed_jobs"] += 1
        elif status == "failed":
            row["failed_jobs"] += 1
        elif status:
            row["in_progress_jobs"] += 1

        if job.machine_score is not None:
            row["_score_sum"] += float(job.machine_score)
            row["_score_count"] += 1

        if job.updated_at and row["last_seen_at"] and job.updated_at.isoformat() > row["last_seen_at"]:
            row["last_seen_at"] = job.updated_at.isoformat()
            row["last_status"] = job.status
            if job.gpu_model:
                row["gpu_model"] = job.gpu_model

        host_is_live = bool(job.host_node_id == node_id and not _is_stale(job.host_heartbeat_at, now))
        row["active_now"] = bool(row["active_now"] or host_is_live)

    summary: list[dict] = []
    for row in by_node.values():
        total = int(row["jobs_total"])
        completed = int(row["completed_jobs"])
        score_count = int(row.pop("_score_count"))
        score_sum = float(row.pop("_score_sum"))
        row["success_rate"] = round((completed / total) * 100, 2) if total else 0.0
        row["avg_machine_score"] = round(score_sum / score_count, 2) if score_count else None
        summary.append(row)

    summary.sort(key=lambda item: (item.get("completed_jobs", 0), item.get("jobs_total", 0)), reverse=True)
    return {
        "timestamp": now.isoformat(),
        "contributors": summary,
    }


@router.get("/contributors/{node_id}/history")
def get_contributor_history(
    node_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    del current_user
    jobs = (
        db.query(Job)
        .filter((Job.latest_host_node_id == node_id) | (Job.host_node_id == node_id))
        .order_by(Job.created_at.desc())
        .limit(limit)
        .all()
    )

    history = [
        {
            "job_id": job.id,
            "repo_url": job.repo_url,
            "branch": job.branch,
            "status": job.status,
            "access_status": job.access_status,
            "machine_score": job.machine_score,
            "failover_count": job.failover_count,
            "checkpoint_phase": job.checkpoint_phase,
            "artifact_state": job.artifact_state,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }
        for job in jobs
    ]

    return {
        "node_id": node_id,
        "count": len(history),
        "history": history,
    }


@router.get("/analytics/daily")
def get_daily_analytics(
    days: int = Query(default=14, ge=3, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    del current_user
    now = datetime.utcnow().date()
    start = now - timedelta(days=days - 1)
    jobs = (
        db.query(Job)
        .filter(Job.created_at >= datetime.combine(start, datetime.min.time()))
        .order_by(Job.created_at.asc())
        .all()
    )

    buckets: dict[str, dict] = {}
    for offset in range(days):
        day = start + timedelta(days=offset)
        key = day.isoformat()
        buckets[key] = {
            "date": key,
            "submitted": 0,
            "completed": 0,
            "failed": 0,
            "contributors": set(),
            "avg_machine_score": None,
            "_score_sum": 0.0,
            "_score_count": 0,
        }

    for job in jobs:
        if not job.created_at:
            continue
        key = job.created_at.date().isoformat()
        if key not in buckets:
            continue
        row = buckets[key]
        row["submitted"] += 1
        status = str(job.status or "")
        if status == "completed":
            row["completed"] += 1
        elif status == "failed":
            row["failed"] += 1

        node_id = str(job.latest_host_node_id or job.host_node_id or "").strip()
        if node_id:
            row["contributors"].add(node_id)

        if job.machine_score is not None:
            row["_score_sum"] += float(job.machine_score)
            row["_score_count"] += 1

    items: list[dict] = []
    for row in buckets.values():
        score_count = int(row.pop("_score_count"))
        score_sum = float(row.pop("_score_sum"))
        row["active_contributors"] = len(row.pop("contributors"))
        row["avg_machine_score"] = round(score_sum / score_count, 2) if score_count else None
        items.append(row)

    return {
        "days": days,
        "series": items,
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
    job.latest_host_node_id = payload.node_id
    job.host_heartbeat_at = datetime.utcnow()
    _bump_session(job)
    if payload.gpu_model is not None:
        job.gpu_model = payload.gpu_model
    if payload.gpu_vram is not None:
        job.gpu_vram = payload.gpu_vram
    if payload.gpu_driver is not None:
        job.gpu_driver = payload.gpu_driver
    if payload.gpu_vram_mb is not None:
        job.gpu_vram_mb = payload.gpu_vram_mb
    if payload.cpu_model is not None:
        job.cpu_model = payload.cpu_model
    if payload.cpu_physical_cores is not None:
        job.cpu_physical_cores = payload.cpu_physical_cores
    if payload.cpu_logical_cores is not None:
        job.cpu_logical_cores = payload.cpu_logical_cores
    if payload.cpu_max_clock_mhz is not None:
        job.cpu_max_clock_mhz = payload.cpu_max_clock_mhz
    if payload.memory_total_mb is not None:
        job.memory_total_mb = payload.memory_total_mb
    if payload.cpu_score is not None:
        job.cpu_score = payload.cpu_score
    if payload.gpu_score is not None:
        job.gpu_score = payload.gpu_score
    if payload.memory_score is not None:
        job.memory_score = payload.memory_score
    if payload.machine_score is not None:
        job.machine_score = payload.machine_score
    if payload.ranking_version is not None:
        job.ranking_version = payload.ranking_version
    if job.status == "queued":
        job.status = "awaiting_receiver"
    db.commit()
    db.refresh(job)
    return {
        "job_id": job.id,
        "host_node_id": job.host_node_id,
        "latest_host_node_id": job.latest_host_node_id,
        "session_version": job.session_version,
        "status": job.status,
    }


@router.post("/jobs/{job_id}/register-receiver")
def register_receiver(
    job_id: str,
    payload: RegisterNodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    _ensure_participant_access(job, current_user)
    if job.access_status != "accepted":
        raise HTTPException(status_code=409, detail="Access must be accepted before receiver can register")
    job.receiver_node_id = payload.node_id
    job.latest_receiver_node_id = payload.node_id
    job.receiver_heartbeat_at = datetime.utcnow()
    _bump_session(job)
    if job.host_node_id:
        job.status = "ready_for_transfer"
    db.commit()
    db.refresh(job)
    return {
        "job_id": job.id,
        "receiver_node_id": job.receiver_node_id,
        "latest_receiver_node_id": job.latest_receiver_node_id,
        "host_node_id": job.host_node_id,
        "latest_host_node_id": job.latest_host_node_id,
        "session_version": job.session_version,
        "artifact_state": job.artifact_state,
        "status": job.status,
    }


@router.post("/jobs/{job_id}/heartbeat")
def heartbeat(
    job_id: str,
    payload: HeartbeatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    _ensure_participant_access(job, current_user)
    now = datetime.utcnow()
    changed = _apply_stale_failover(job, now)

    role = (payload.role or "").strip().lower()
    node_id = (payload.node_id or "").strip()
    if not node_id:
        raise HTTPException(status_code=400, detail="node_id is required")
    if role not in {"host", "receiver"}:
        raise HTTPException(status_code=400, detail="role must be 'host' or 'receiver'")

    if role == "host":
        if not job.host_node_id:
            job.host_node_id = node_id
            _bump_session(job)
            changed = True
        job.latest_host_node_id = node_id
        job.host_heartbeat_at = now
        if job.access_status == "accepted" and job.status == "queued":
            job.status = "awaiting_receiver"
            changed = True
        if job.last_failover_reason == "host_heartbeat_timeout":
            job.last_failover_reason = None
            changed = True
    else:
        if not job.receiver_node_id:
            job.receiver_node_id = node_id
            _bump_session(job)
            changed = True
        job.latest_receiver_node_id = node_id
        job.receiver_heartbeat_at = now
        if job.host_node_id and job.status in {"awaiting_receiver", "queued", "ready_for_transfer"}:
            job.status = "ready_for_transfer"
            changed = True
        if job.last_failover_reason == "receiver_heartbeat_timeout":
            job.last_failover_reason = None
            changed = True

    if changed:
        db.commit()
        db.refresh(job)

    return {
        "job_id": job.id,
        "status": job.status,
        "artifact_state": job.artifact_state,
        "session_version": job.session_version,
        "host_node_id": job.host_node_id,
        "receiver_node_id": job.receiver_node_id,
        "host_heartbeat_at": job.host_heartbeat_at.isoformat() if job.host_heartbeat_at else None,
        "receiver_heartbeat_at": job.receiver_heartbeat_at.isoformat() if job.receiver_heartbeat_at else None,
        "failover_count": job.failover_count,
        "last_failover_reason": job.last_failover_reason,
        "checkpoint_phase": job.checkpoint_phase,
        "checkpoint_data": job.checkpoint_data,
        "checkpoint_updated_at": job.checkpoint_updated_at.isoformat() if job.checkpoint_updated_at else None,
    }


@router.post("/jobs/{job_id}/checkpoint")
def update_checkpoint(
    job_id: str,
    payload: CheckpointUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    _ensure_participant_access(job, current_user)

    role = (payload.role or "").strip().lower()
    phase = (payload.phase or "").strip()
    if role not in {"host", "receiver"}:
        raise HTTPException(status_code=400, detail="role must be 'host' or 'receiver'")
    if not phase:
        raise HTTPException(status_code=400, detail="phase is required")

    checkpoint_payload = {
        "role": role,
        "phase": phase,
        "data": payload.data or {},
        "recorded_at": datetime.utcnow().isoformat(),
    }
    job.checkpoint_phase = f"{role}:{phase}"
    job.checkpoint_data = json.dumps(checkpoint_payload)
    job.checkpoint_updated_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    checkpoint_updated_at = job.checkpoint_updated_at

    return {
        "job_id": job.id,
        "checkpoint_phase": job.checkpoint_phase,
        "checkpoint_data": job.checkpoint_data,
        "checkpoint_updated_at": checkpoint_updated_at.isoformat() if checkpoint_updated_at is not None else None,
    }


@router.get("/jobs/{job_id}/peers")
def get_job_peers(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    _ensure_participant_access(job, current_user)
    if _apply_stale_failover(job, datetime.utcnow()):
        db.commit()
        db.refresh(job)
    return {
        "job_id": job.id,
        "host_node_id": job.host_node_id,
        "receiver_node_id": job.receiver_node_id,
        "latest_host_node_id": job.latest_host_node_id or job.host_node_id,
        "latest_receiver_node_id": job.latest_receiver_node_id or job.receiver_node_id,
        "session_version": job.session_version,
        "artifact_state": job.artifact_state,
        "host_heartbeat_at": job.host_heartbeat_at.isoformat() if job.host_heartbeat_at else None,
        "receiver_heartbeat_at": job.receiver_heartbeat_at.isoformat() if job.receiver_heartbeat_at else None,
        "failover_count": job.failover_count,
        "last_failover_reason": job.last_failover_reason,
        "checkpoint_phase": job.checkpoint_phase,
        "checkpoint_data": job.checkpoint_data,
        "checkpoint_updated_at": job.checkpoint_updated_at.isoformat() if job.checkpoint_updated_at else None,
        "ready": bool(job.host_node_id and job.receiver_node_id),
        "status": job.status,
    }


@router.post("/jobs/{job_id}/artifact-state")
def update_artifact_state(
    job_id: str,
    payload: ArtifactStateUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_job(job_id, db)
    _ensure_participant_access(job, current_user)
    allowed = {"PENDING", "READY_FOR_TRANSFER", "DELIVERED"}
    next_state = (payload.artifact_state or "").strip().upper()
    if next_state not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid artifact_state '{payload.artifact_state}'")
    job.artifact_state = next_state
    db.commit()
    db.refresh(job)
    return {
        "job_id": job.id,
        "artifact_state": job.artifact_state,
        "session_version": job.session_version,
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
    if payload.success:
        job.artifact_state = "DELIVERED"
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
