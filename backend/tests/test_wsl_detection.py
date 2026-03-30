"""Unit tests for _is_wsl with mocked /proc/version — no WSL required."""
import sys
import os
from unittest.mock import patch, mock_open

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.p2p_cli import _is_wsl


def _mock_proc_version(content: str):
    return patch("builtins.open", mock_open(read_data=content))


def test_wsl_detected_microsoft_kernel(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    mock_path_read = patch(
        "app.core.p2p_cli.Path.read_text",
        return_value="Linux version 5.15.90.1-microsoft-standard-WSL2",
    )
    with mock_path_read:
        assert _is_wsl() is True


def test_wsl_detected_wsl_in_version(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    mock_path_read = patch(
        "app.core.p2p_cli.Path.read_text",
        return_value="Linux version 4.4.0-19041-Microsoft (WSL)",
    )
    with mock_path_read:
        assert _is_wsl() is True


def test_not_wsl_on_native_linux(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    mock_path_read = patch(
        "app.core.p2p_cli.Path.read_text",
        return_value="Linux version 6.1.0-21-amd64 (debian-kernel@lists.debian.org)",
    )
    with mock_path_read:
        assert _is_wsl() is False


def test_not_wsl_on_macos(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    assert _is_wsl() is False


def test_not_wsl_on_windows(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Windows")
    assert _is_wsl() is False


def test_not_wsl_when_proc_version_missing(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    mock_path_read = patch(
        "app.core.p2p_cli.Path.read_text",
        side_effect=OSError("no such file"),
    )
    with mock_path_read:
        assert _is_wsl() is False
