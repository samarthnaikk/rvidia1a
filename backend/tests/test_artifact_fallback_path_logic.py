"""Unit tests for _download_ticket_to_path fallback logic — no iroh daemon required."""
import asyncio
import sys
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.core.p2p_cli as p2p_cli


def _make_fake_node():
    node = MagicMock()
    node._endpoint_owner = MagicMock()
    blobs = MagicMock()
    node._endpoint_owner.blobs = MagicMock(return_value=blobs)
    return node, blobs


def _make_ticket_mock():
    ticket = MagicMock()
    ticket.hash.return_value = "fakehash"
    ticket.as_download_options.return_value = MagicMock()
    return ticket


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_primary_write_succeeds():
    """When primary write_to_path succeeds, the artifact is at the requested path."""
    node, blobs = _make_fake_node()
    blobs.download = AsyncMock()
    blobs.write_to_path = AsyncMock()

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "artifact.txt"
        with patch("iroh.BlobTicket", return_value=_make_ticket_mock()):
            result = run(p2p_cli._download_ticket_to_path(node, "faketicket", dest))
        assert result == dest.resolve()


def test_primary_fails_temp_copy_succeeds():
    """When primary write fails, the artifact is written to temp and copied to destination."""
    node, blobs = _make_fake_node()
    blobs.download = AsyncMock()

    call_count = {"n": 0}

    async def _write_to_path(hash_, path_str):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise Exception("IrohError: cannot write to /mnt/c/...")
        # Second call (temp path) writes an actual file so shutil.copy2 has something to copy.
        Path(path_str).write_bytes(b"fake artifact content")

    blobs.write_to_path = _write_to_path

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "artifact.txt"
        with patch("iroh.BlobTicket", return_value=_make_ticket_mock()):
            result = run(p2p_cli._download_ticket_to_path(node, "faketicket", dest))
        assert result == dest.resolve()
        assert dest.read_bytes() == b"fake artifact content"


def test_both_writes_fail_raises_with_context():
    """When both primary and temp writes fail, RuntimeError includes both errors."""
    node, blobs = _make_fake_node()
    blobs.download = AsyncMock()

    async def _always_fail(hash_, path_str):
        raise Exception("IrohError: cannot write")

    blobs.write_to_path = _always_fail

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "artifact.txt"
        with patch("iroh.BlobTicket", return_value=_make_ticket_mock()):
            try:
                run(p2p_cli._download_ticket_to_path(node, "faketicket", dest))
                assert False, "Expected RuntimeError"
            except RuntimeError as exc:
                assert "primary" in str(exc).lower() or "temp path" in str(exc).lower()


def test_temp_write_succeeds_but_copy_fails_raises_with_temp_path():
    """When temp write succeeds but copy fails, error includes the temp file path for recovery."""
    node, blobs = _make_fake_node()
    blobs.download = AsyncMock()

    call_count = {"n": 0}

    async def _write_to_path(hash_, path_str):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise Exception("IrohError: cannot write to /mnt/c/...")
        Path(path_str).write_bytes(b"data")

    blobs.write_to_path = _write_to_path

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "sub" / "artifact.txt"
        # Make copy fail by patching shutil.copy2
        with patch("app.core.p2p_cli.shutil.copy2", side_effect=OSError("permission denied")):
            with patch("iroh.BlobTicket", return_value=_make_ticket_mock()):
                try:
                    run(p2p_cli._download_ticket_to_path(node, "faketicket", dest))
                    assert False, "Expected RuntimeError"
                except RuntimeError as exc:
                    assert "recover manually" in str(exc).lower() or "temp path" in str(exc).lower()
