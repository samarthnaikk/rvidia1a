"""Tests: DB-backed P2P signal persistence and targeted delivery."""
from datetime import datetime
from uuid import uuid4

import pytest

from app.models.p2p_signal import P2PSignal


def _make_signal(db, job_id, from_node, to_node, payload="{}"):
    sig = P2PSignal(
        id=str(uuid4()),
        job_id=job_id,
        from_node_id=from_node,
        to_node_id=to_node,
        signal_type="offer",
        payload=payload,
        delivered=False,
        created_at=datetime.utcnow(),
    )
    db.add(sig)
    db.commit()
    return sig


def _pull(db, job_id, to_node):
    rows = (
        db.query(P2PSignal)
        .filter(
            P2PSignal.job_id == job_id,
            P2PSignal.to_node_id == to_node,
            P2PSignal.delivered == False,  # noqa: E712
        )
        .order_by(P2PSignal.created_at.asc())
        .all()
    )
    now = datetime.utcnow()
    for row in rows:
        row.delivered = True
        row.delivered_at = now
    if rows:
        db.commit()
    return rows


def test_pushed_signal_is_retrievable_in_new_query(db_session):
    """Signal persisted in DB must be retrievable in a subsequent query."""
    job_id = str(uuid4())
    _make_signal(db_session, job_id, "host-A", "renter-B", '{"type":"result_ticket"}')

    rows = _pull(db_session, job_id, "renter-B")
    assert len(rows) == 1
    assert rows[0].payload == '{"type":"result_ticket"}'


def test_signal_only_delivered_to_target_node(db_session):
    """Signal addressed to node-B must NOT appear in node-C's pull."""
    job_id = str(uuid4())
    _make_signal(db_session, job_id, "host-A", "renter-B", '{"type":"input_ticket"}')

    rows_c = _pull(db_session, job_id, "renter-C")
    assert rows_c == [], "node-C should receive nothing"

    rows_b = _pull(db_session, job_id, "renter-B")
    assert len(rows_b) == 1


def test_delivered_rows_not_re_delivered(db_session):
    """After a signal is pulled and marked delivered, a second pull returns nothing."""
    job_id = str(uuid4())
    _make_signal(db_session, job_id, "host-A", "renter-B", '{"type":"result_ticket"}')

    first_pull = _pull(db_session, job_id, "renter-B")
    assert len(first_pull) == 1

    second_pull = _pull(db_session, job_id, "renter-B")
    assert second_pull == [], "already-delivered rows must not be returned again"


def test_multiple_signals_ordered_by_created_at(db_session):
    """Multiple signals must be returned in created_at ascending order."""
    import time

    job_id = str(uuid4())
    _make_signal(db_session, job_id, "host", "renter", '{"seq":1}')
    time.sleep(0.01)
    _make_signal(db_session, job_id, "host", "renter", '{"seq":2}')
    time.sleep(0.01)
    _make_signal(db_session, job_id, "host", "renter", '{"seq":3}')

    rows = _pull(db_session, job_id, "renter")
    assert len(rows) == 3
    import json
    payloads = [json.loads(r.payload)["seq"] for r in rows]
    assert payloads == [1, 2, 3]
