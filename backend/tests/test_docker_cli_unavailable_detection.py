"""Unit tests for Docker CLI unavailable detection in host logs."""

from app.core.p2p_cli import _is_docker_cli_unavailable


def test_detects_wsl_missing_docker_message() -> None:
    text = "The command 'docker' could not be found in this WSL 2 distro."
    assert _is_docker_cli_unavailable(text)


def test_detects_linux_command_not_found() -> None:
    text = "docker: command not found"
    assert _is_docker_cli_unavailable(text)


def test_does_not_false_positive_on_regular_build_failure() -> None:
    text = "ERROR: failed to solve: process '/bin/sh -c pip install -r requirements.txt' did not complete successfully"
    assert not _is_docker_cli_unavailable(text)
