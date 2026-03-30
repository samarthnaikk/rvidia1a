"""Unit tests for _is_gpu_runtime_unavailable — no Docker daemon required."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.p2p_cli import _is_gpu_runtime_unavailable


def test_detects_device_driver_error():
    assert _is_gpu_runtime_unavailable("could not select device driver")


def test_detects_capabilities_gpu():
    assert _is_gpu_runtime_unavailable("Error response from daemon: could not select device driver capabilities: [[gpu]]")


def test_detects_nvidia_container_cli():
    assert _is_gpu_runtime_unavailable("nvidia-container-cli: initialization error: ...")


def test_detects_wsl_no_adapters():
    assert _is_gpu_runtime_unavailable("WSL environment detected but no adapters were found")


def test_detects_wsl_no_adapters_case_insensitive():
    assert _is_gpu_runtime_unavailable("wsl environment detected but no adapters were found")


def test_detects_no_cuda_device():
    assert _is_gpu_runtime_unavailable("no cuda-capable device is detected")


def test_detects_unknown_runtime():
    assert _is_gpu_runtime_unavailable("Unknown runtime specified nvidia")


def test_detects_could_not_load_nvml():
    assert _is_gpu_runtime_unavailable("could not load nvml library")


def test_does_not_false_positive_on_oom():
    assert not _is_gpu_runtime_unavailable("Container exited: out of memory")


def test_does_not_false_positive_on_empty():
    assert not _is_gpu_runtime_unavailable("")


def test_multiline_log_with_signal():
    log = (
        "Step 1/4 : FROM python:3.11-slim\n"
        "Step 2/4 : RUN pip install torch\n"
        "docker: Error response from daemon: WSL environment detected but no adapters were found.\n"
        "exit code 125\n"
    )
    assert _is_gpu_runtime_unavailable(log)
