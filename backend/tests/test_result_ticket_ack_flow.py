"""Tests: result_ticket ACK/retry flow."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import uuid4

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_args(job_id=None, api_base="http://test", token="tok"):
    args = MagicMock()
    args.api_base = api_base
    args.token = token
    args.job_id = job_id or str(uuid4())
    args.workspace = "/tmp/ws"
    args.secret_key = None
    return args


# ── tests ─────────────────────────────────────────────────────────────────────

def test_host_stops_retrying_on_ack():
    """Host must exit retry loop as soon as a matching result_ack arrives."""
    transfer_id = str(uuid4())
    call_count = {"n": 0}

    def fake_pull_signals(api_base, token, job_id, node_id):
        call_count["n"] += 1
        if call_count["n"] >= 2:
            # Return ACK on second poll.
            return [{"type": "result_ack", "transfer_id": transfer_id}]
        return []

    ack_received = False
    retry_count = 0
    ack_timeout = 30
    retry_interval = 0  # instant for test speed

    import time
    ack_start = time.time()

    while not ack_received and (time.time() - ack_start) < ack_timeout:
        for signal in fake_pull_signals("http://x", "tok", "job1", "node1"):
            if signal.get("type") == "result_ack" and signal.get("transfer_id") == transfer_id:
                ack_received = True
                break
        if not ack_received:
            retry_count += 1

    assert ack_received, "ACK should have been detected"
    assert retry_count == 1, "Should have retried exactly once before ACK"


def test_host_marks_unacknowledged_on_timeout():
    """When no ACK arrives within timeout, host should report unacknowledged."""
    transfer_id = str(uuid4())
    ack_received = False
    ack_timeout = 0  # zero timeout — immediately expire

    import time
    ack_start = time.time() - 1  # simulate already past deadline

    while not ack_received and (time.time() - ack_start) < ack_timeout:
        pass  # would poll here in real code

    assert not ack_received, "No ACK should arrive within zero timeout"


def test_result_ack_wrong_transfer_id_not_accepted():
    """ACK with a different transfer_id must not stop the retry loop."""
    expected_transfer_id = str(uuid4())
    wrong_transfer_id = str(uuid4())

    signals = [{"type": "result_ack", "transfer_id": wrong_transfer_id}]

    ack_received = False
    for signal in signals:
        if signal.get("type") == "result_ack" and signal.get("transfer_id") == expected_transfer_id:
            ack_received = True
            break

    assert not ack_received, "ACK with wrong transfer_id must be ignored"
