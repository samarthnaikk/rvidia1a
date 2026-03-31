"""Unit tests for auto receiver launch config resolution in client CLI."""

from unittest.mock import patch

from app.core.client_cli import _resolve_receiver_launch_config


def test_auto_resolution_uses_access_payload_repo_branch_and_host() -> None:
    payload = {
        "repo_url": "https://github.com/example/repo",
        "branch": "main",
        "latest_host_node_id": "host-123",
    }

    with patch("app.core.client_cli._api_request", return_value=payload):
        repo, branch, host = _resolve_receiver_launch_config(
            api_base="http://localhost:8000",
            token="token",
            job_id="job-1",
            repo_url="",
            branch="main",
            host_node_id="",
            auto=True,
        )

    assert repo == "https://github.com/example/repo"
    assert branch == "main"
    assert host == "host-123"


def test_manual_repo_without_auto_skips_lookup() -> None:
    with patch("app.core.client_cli._api_request") as mocked:
        repo, branch, host = _resolve_receiver_launch_config(
            api_base="http://localhost:8000",
            token="token",
            job_id="job-1",
            repo_url="https://github.com/manual/repo",
            branch="dev",
            host_node_id="",
            auto=False,
        )

    mocked.assert_not_called()
    assert repo == "https://github.com/manual/repo"
    assert branch == "dev"
    assert host == ""


def test_auto_resolution_raises_when_repo_missing() -> None:
    payload = {
        "repo_url": "",
        "branch": "main",
        "latest_host_node_id": "host-123",
    }

    with patch("app.core.client_cli._api_request", return_value=payload):
        try:
            _resolve_receiver_launch_config(
                api_base="http://localhost:8000",
                token="token",
                job_id="job-1",
                repo_url="",
                branch="main",
                host_node_id="",
                auto=True,
            )
            assert False, "Expected RuntimeError"
        except RuntimeError as exc:
            assert "repo_url" in str(exc)
