from app.models.job import Job
from app.models.user import User
from app.routes.p2p import accept_access, get_access_state, list_access_requests, request_access
from app.schemas.job import AcceptAccessRequest, AccessRequestPayload


def _create_user(db_session, username: str, email: str) -> User:
    user = User(username=username, email=email, password_hash="hash")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_request_access_stores_hardware_metadata(db_session):
    owner = _create_user(db_session, "owner", "owner@example.com")
    requester = _create_user(db_session, "host1", "host1@example.com")

    job = Job(user_id=owner.id, filename="", command="", status="queued")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    payload = AccessRequestPayload(
        hardware_metadata={
            "cpu_model": "Intel Core i9-14900K",
            "gpu_model": "RTX 4090",
            "gpu_vram_mb": 24576,
            "ram_mb": 32768,
            "total_score": 97.4,
        }
    )
    response = request_access(job_id=job.id, payload=payload, db=db_session, current_user=requester)
    assert response["request_id"]
    assert response["total_score"] == 97.4

    owner_view = list_access_requests(job_id=job.id, db=db_session, current_user=owner)
    assert owner_view["requests"][0]["cpu_model"] == "Intel Core i9-14900K"
    assert owner_view["requests"][0]["gpu_model"] == "RTX 4090"
    assert owner_view["requests"][0]["ram_mb"] == 32768


def test_accept_access_returns_sorted_accepted_hosts(db_session):
    owner = _create_user(db_session, "owner2", "owner2@example.com")
    requester_a = _create_user(db_session, "host2", "host2@example.com")
    requester_b = _create_user(db_session, "host3", "host3@example.com")

    job = Job(user_id=owner.id, filename="", command="", status="queued")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    request_access(
        job_id=job.id,
        payload=AccessRequestPayload(hardware_metadata={"cpu_model": "A", "total_score": 55.0}),
        db=db_session,
        current_user=requester_a,
    )
    request_access(
        job_id=job.id,
        payload=AccessRequestPayload(hardware_metadata={"cpu_model": "B", "total_score": 88.0}),
        db=db_session,
        current_user=requester_b,
    )

    accept_access(
        job_id=job.id,
        payload=AcceptAccessRequest(requester_user_id=requester_a.id),
        db=db_session,
        current_user=owner,
    )
    accepted_response = accept_access(
        job_id=job.id,
        payload=AcceptAccessRequest(requester_user_id=requester_b.id),
        db=db_session,
        current_user=owner,
    )
    accepted = accepted_response["accepted_hosts"]
    assert accepted[0]["requester_user_id"] == requester_b.id
    assert accepted[1]["requester_user_id"] == requester_a.id
    assert accepted[0]["rank"] == 1
    assert accepted[1]["rank"] == 2


def test_access_state_is_per_requester_when_multiple_requests_exist(db_session):
    owner = _create_user(db_session, "owner3", "owner3@example.com")
    accepted = _create_user(db_session, "accepted_user", "accepted@example.com")
    pending = _create_user(db_session, "pending_user", "pending@example.com")

    job = Job(user_id=owner.id, filename="", command="", status="queued")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    request_access(
        job_id=job.id,
        payload=AccessRequestPayload(hardware_metadata={"total_score": 80.0}),
        db=db_session,
        current_user=accepted,
    )
    request_access(
        job_id=job.id,
        payload=AccessRequestPayload(hardware_metadata={"total_score": 60.0}),
        db=db_session,
        current_user=pending,
    )
    accept_access(
        job_id=job.id,
        payload=AcceptAccessRequest(requester_user_id=accepted.id),
        db=db_session,
        current_user=owner,
    )

    accepted_state = get_access_state(job_id=job.id, db=db_session, current_user=accepted)
    pending_state = get_access_state(job_id=job.id, db=db_session, current_user=pending)
    assert accepted_state["access_status"] == "accepted"
    assert pending_state["access_status"] == "requested"
