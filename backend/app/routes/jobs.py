from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import Job
from app.models.user import User
from app.routes.auth import get_current_user
from app.schemas.job import (
    JobCompletionRequest,
    JobCreateRequest,
    JobResponse,
    JobUpdateStatusRequest,
)

router = APIRouter()


@router.post("", response_model=JobResponse)
def create_job(
    payload: JobCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = Job(
        user_id=current_user.id,
        filename=payload.filename,
        command=payload.command,
        repo_url=payload.repo_url if hasattr(payload, "repo_url") else None,
        branch=getattr(payload, "branch", "main"),
        status="queued",
        receiver_node_id=f"receiver-user-{current_user.id}",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("", response_model=list[JobResponse])
def list_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Job)
        .filter(Job.user_id == current_user.id)
        .order_by(Job.created_at.desc())
        .all()
    )


@router.get("/open", response_model=list[JobResponse])
def list_open_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Job)
        .filter(Job.status.in_(["queued", "awaiting_receiver", "ready_for_transfer", "transferring"]))
        .order_by(Job.created_at.desc())
        .all()
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/{job_id}/status", response_model=JobResponse)
def update_job_status(
    job_id: str,
    payload: JobUpdateStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = payload.status
    job.error_message = payload.error_message
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/complete", response_model=JobResponse)
def complete_job(
    job_id: str,
    payload: JobCompletionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = "completed" if payload.success else "failed"
    job.artifact_name = payload.artifact_name
    job.artifact_path = payload.artifact_path
    job.error_message = payload.error_message
    db.commit()
    db.refresh(job)
    return job
