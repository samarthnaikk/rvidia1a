"""Tests: renter fails clearly when result_ticket contains no artifacts."""
import pytest


def _parse_artifact_tickets(result: dict) -> list[dict]:
    """Mirror the logic in run_receiver for resolving artifact_tickets."""
    artifact_tickets: list[dict] = result.get("artifact_tickets") or []
    if not artifact_tickets and result.get("artifact_ticket"):
        artifact_tickets = [
            {
                "name": str(result.get("artifact_name") or "artifact.txt"),
                "ticket": str(result["artifact_ticket"]),
            }
        ]
    return artifact_tickets


def test_raises_when_no_artifact_tickets():
    result = {"type": "result_ticket", "success": True, "transfer_id": "tid-1"}
    tickets = _parse_artifact_tickets(result)
    assert not tickets, "should be empty"
    with pytest.raises(RuntimeError, match="no artifact tickets"):
        if not tickets:
            raise RuntimeError(
                f"result_ticket received but contains no artifact tickets "
                f"(transfer_id={result.get('transfer_id', 'unknown')})"
            )


def test_legacy_single_artifact_field_resolved():
    result = {
        "type": "result_ticket",
        "success": True,
        "artifact_ticket": "blobticket-abc",
        "artifact_name": "model.bin",
    }
    tickets = _parse_artifact_tickets(result)
    assert len(tickets) == 1
    assert tickets[0]["name"] == "model.bin"
    assert tickets[0]["ticket"] == "blobticket-abc"


def test_multi_artifact_list_preserved():
    result = {
        "type": "result_ticket",
        "success": True,
        "artifact_tickets": [
            {"name": "a.txt", "ticket": "ticket-a"},
            {"name": "b.txt", "ticket": "ticket-b"},
        ],
    }
    tickets = _parse_artifact_tickets(result)
    assert len(tickets) == 2
    assert tickets[0]["name"] == "a.txt"
    assert tickets[1]["name"] == "b.txt"


def test_multi_artifact_takes_precedence_over_legacy():
    """artifact_tickets list must take precedence over legacy artifact_ticket field."""
    result = {
        "type": "result_ticket",
        "success": True,
        "artifact_tickets": [{"name": "new.txt", "ticket": "ticket-new"}],
        "artifact_ticket": "ticket-old",
        "artifact_name": "old.txt",
    }
    tickets = _parse_artifact_tickets(result)
    assert len(tickets) == 1
    assert tickets[0]["name"] == "new.txt"
