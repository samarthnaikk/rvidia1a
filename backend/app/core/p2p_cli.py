import argparse
import asyncio
import contextlib
import hashlib
import inspect
import json
import os
import platform
import shlex
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Sequence
from urllib import error, request
from urllib.parse import urlsplit, urlunsplit

import iroh

from app.core.rvidia_core import RvidiaNode, WorkspaceManager


DEFAULT_API_BASE = "http://157.180.74.2"
DEFAULT_WORKSPACE = "./.p2p-workspaces"

_RECONNECT_INTERVAL = 5  # seconds between reconnect attempts
_ACK_POLL_INTERVAL = 2
_RESULT_RETRY_INTERVAL = 5
_DELIVERY_TIMEOUT_SECONDS = 20 * 60
_HEARTBEAT_INTERVAL_SECONDS = 10


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _normalize_api_base(api_base: str) -> str:
    normalized = (api_base or "").strip().rstrip("/")
    if not normalized:
        return normalized

    parsed = urlsplit(normalized)
    host = (parsed.hostname or "").lower()
    port = parsed.port

    # Common mistake: passing frontend dev server to CLI.
    # Auto-correct localhost frontend ports to FastAPI backend port.
    if host in {"localhost", "127.0.0.1"} and port in {3000, 4173, 5173}:
        corrected_netloc = f"{host}:8000"
        corrected = urlunsplit((parsed.scheme or "http", corrected_netloc, parsed.path, parsed.query, parsed.fragment))
        print(
            f"[RVIDIA] --api-base '{normalized}' looks like a frontend dev server; "
            f"using backend '{corrected.rstrip('/')}' instead.",
            file=sys.stderr,
        )
        return corrected.rstrip("/")

    return normalized


def _build_api_url(api_base: str, path: str, with_api_prefix: bool = False) -> str:
    base = _normalize_api_base(api_base)
    if with_api_prefix and not base.endswith("/api"):
        base = f"{base}/api"
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{base}{normalized_path}"


def _api_request(method: str, api_base: str, path: str, token: str, payload: dict | None = None) -> Any:
    encoded_body = None
    if payload is not None:
        encoded_body = json.dumps(payload).encode("utf-8")

    def _perform(url: str) -> tuple[bytes, str]:
        req = request.Request(
            url=url,
            method=method,
            headers=_auth_headers(token),
            data=encoded_body,
        )
        with request.urlopen(req, timeout=30) as response:
            return response.read(), response.headers.get("Content-Type", "")

    primary_url = _build_api_url(api_base, path, with_api_prefix=False)
    used_url = primary_url
    content_type = ""

    try:
        raw, content_type = _perform(primary_url)
    except error.HTTPError as exc:
        if exc.code == 404:
            fallback_url = _build_api_url(api_base, path, with_api_prefix=True)
            if fallback_url != primary_url:
                try:
                    used_url = fallback_url
                    raw, content_type = _perform(fallback_url)
                except error.HTTPError as fallback_exc:
                    details = fallback_exc.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"API error {fallback_exc.code}: {details}") from fallback_exc
                except error.URLError as fallback_exc:
                    raise RuntimeError(f"API connection error: {fallback_exc.reason}") from fallback_exc
            else:
                details = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"API error {exc.code}: {details}") from exc
        else:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"API error {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"API connection error: {exc.reason}") from exc

    if not raw:
        return {}

    body_text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(body_text)
    except json.JSONDecodeError as exc:
        compact = " ".join(body_text.split())
        snippet = compact[:220]
        hint = ""
        if "text/html" in content_type.lower() or body_text.lstrip().startswith("<"):
            hint = " Hint: this looks like an HTML page. Check --api-base points to backend (e.g. http://localhost:8000)."
        raise RuntimeError(
            f"API returned non-JSON response from {used_url} (Content-Type: {content_type or 'unknown'}). "
            f"Body preview: {snippet!r}.{hint}"
        ) from exc


def _api_post(api_base: str, path: str, token: str, payload: dict) -> Any:
    return _api_request("POST", api_base, path, token, payload)


def _api_patch(api_base: str, path: str, token: str, payload: dict) -> Any:
    return _api_request("PATCH", api_base, path, token, payload)


def _api_get(api_base: str, path: str, token: str) -> Any:
    return _api_request("GET", api_base, path, token)


def _api_set_artifact_state(api_base: str, token: str, job_id: str, artifact_state: str) -> dict[str, Any]:
    payload = _api_post(
        api_base,
        f"/p2p/jobs/{job_id}/artifact-state",
        token,
        {"artifact_state": artifact_state},
    )
    return payload if isinstance(payload, dict) else {}


def _api_set_checkpoint(
    api_base: str,
    token: str,
    job_id: str,
    role: str,
    phase: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        payload = _api_post(
            api_base,
            f"/p2p/jobs/{job_id}/checkpoint",
            token,
            {
                "role": role,
                "phase": phase,
                "data": data or {},
            },
        )
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        print(f"[RVIDIA] checkpoint warning ({role}:{phase}): {exc}", file=sys.stderr)
        return {}


def _list_marketplace_jobs(api_base: str, token: str) -> list[dict[str, Any]]:
    payload = _api_get(api_base, "/p2p/jobs", token)
    return payload if isinstance(payload, list) else []


def _get_access_state(api_base: str, token: str, job_id: str) -> dict[str, Any]:
    payload = _api_get(api_base, f"/p2p/jobs/{job_id}/access", token)
    return payload if isinstance(payload, dict) else {}


def _resolve_requested_job_id(api_base: str, token: str, requested_job_id: str) -> str:
    normalized = (requested_job_id or "").strip()
    if not normalized:
        raise RuntimeError("Missing --job-id")

    if normalized.lower() not in {"latest", "auto"}:
        return normalized

    jobs = _list_marketplace_jobs(api_base, token)
    if not jobs:
        raise RuntimeError("No marketplace jobs available to resolve --job-id latest")

    job_id = str(jobs[0].get("job_id") or "").strip()
    if not job_id:
        raise RuntimeError("Unable to resolve job_id from marketplace payload")
    print(f"[RVIDIA] Resolved --job-id {normalized!r} to '{job_id}'")
    return job_id


def _job_not_found_hint(api_base: str, token: str, requested_job_id: str) -> str:
    try:
        jobs = _list_marketplace_jobs(api_base, token)
    except Exception as exc:
        return (
            f"Job '{requested_job_id}' was not found and marketplace lookup failed: {exc}. "
            "Retry with --job-id latest."
        )

    ids: list[str] = []
    for job in jobs:
        value = str(job.get("job_id") or "").strip()
        if value:
            ids.append(value)

    if not ids:
        return (
            f"Job '{requested_job_id}' was not found and no marketplace jobs are visible for this token/backend. "
            "Create/accept a job first, then retry."
        )

    preview = ", ".join(ids[:5])
    return (
        f"Job '{requested_job_id}' was not found on {api_base}. "
        f"Visible job_id values (first {min(len(ids), 5)}): {preview}. "
        "Use one of these IDs or pass --job-id latest."
    )


async def _wait_for_access_accepted(api_base: str, token: str, job_id: str) -> None:
    while True:
        state = _get_access_state(api_base, token, job_id)
        status = str(state.get("access_status") or "")
        if status == "accepted":
            return
        if status == "open":
            raise RuntimeError("Access request is still open; requester must call request-access first")
        print(f"[RVIDIA] Waiting for access acceptance (current: {status or 'unknown'})...")
        await asyncio.sleep(2)


async def _heartbeat_loop(args, role: str, node_id: str) -> None:
    while True:
        try:
            _api_post(
                args.api_base,
                f"/p2p/jobs/{args.job_id}/heartbeat",
                args.token,
                {"node_id": node_id, "role": role},
            )
        except Exception as exc:
            print(f"[RVIDIA] heartbeat warning ({role}): {exc}", file=sys.stderr)
        await asyncio.sleep(_HEARTBEAT_INTERVAL_SECONDS)


# â”€â”€ GPU Detection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _detect_gpu() -> dict[str, str | None]:
    """Detect GPU details via nvidia-smi. Falls back gracefully on missing GPU."""
    try:
        import subprocess
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            if len(parts) >= 3:
                return {
                    "gpu_model": parts[0],
                    "gpu_vram": f"{parts[1]} MiB",
                    "gpu_driver": parts[2],
                }
    except Exception:
        pass

    try:
        import pynvml  # type: ignore[import]
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode()
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        driver = pynvml.nvmlSystemGetDriverVersion()
        if isinstance(driver, bytes):
            driver = driver.decode()
        return {
            "gpu_model": name,
            "gpu_vram": f"{mem.total // 1024 // 1024} MiB",
            "gpu_driver": driver,
        }
    except Exception:
        pass

    return {"gpu_model": None, "gpu_vram": None, "gpu_driver": None}


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _parse_gpu_vram_mb(gpu_vram: str | None) -> int | None:
    if not gpu_vram:
        return None
    digits = "".join(ch for ch in str(gpu_vram) if ch.isdigit())
    return _safe_int(digits)


def _memory_total_mb() -> int | None:
    try:
        if platform.system() == "Darwin":
            import subprocess

            result = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                bytes_value = _safe_int(result.stdout.strip())
                if bytes_value:
                    return int(bytes_value / (1024 * 1024))
        if hasattr(os, "sysconf") and "SC_PAGE_SIZE" in os.sysconf_names and "SC_PHYS_PAGES" in os.sysconf_names:
            page_size = os.sysconf("SC_PAGE_SIZE")
            pages = os.sysconf("SC_PHYS_PAGES")
            if isinstance(page_size, int) and isinstance(pages, int) and page_size > 0 and pages > 0:
                return int((page_size * pages) / (1024 * 1024))
    except Exception:
        return None
    return None


def _clamp_score(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 100:
        return 100.0
    return round(value, 2)


def _keyword_score(name: str | None, tiers: Sequence[tuple[str, float]]) -> float:
    if not name:
        return 0.0
    lowered = name.lower()
    for key, score in tiers:
        if key in lowered:
            return score
    return 0.0


def _build_machine_profile(gpu_info: dict[str, str | None]) -> dict[str, Any]:
    cpu_model = platform.processor() or platform.machine() or platform.platform()
    logical = _safe_int(os.cpu_count())
    physical = logical
    if logical and logical > 1:
        physical = max(1, int(logical / 2))

    memory_total_mb = _memory_total_mb()
    gpu_vram_mb = _parse_gpu_vram_mb(gpu_info.get("gpu_vram"))

    cpu_tiers = [
        ("threadripper", 35),
        ("xeon", 30),
        ("epyc", 35),
        ("ryzen 9", 28),
        ("ryzen 7", 24),
        ("core i9", 26),
        ("core i7", 22),
        ("apple", 22),
    ]
    gpu_tiers = [
        ("rtx 4090", 70),
        ("rtx 3090", 62),
        ("rtx", 55),
        ("a100", 75),
        ("h100", 80),
        ("radeon", 42),
        ("apple", 34),
        ("intel", 22),
    ]

    cpu_score = _clamp_score((physical or 0) * 3 + (logical or 0) * 1.5 + _keyword_score(cpu_model, cpu_tiers))
    gpu_score = _clamp_score((gpu_vram_mb or 0) / 256 + _keyword_score(gpu_info.get("gpu_model"), gpu_tiers))
    memory_score = _clamp_score((memory_total_mb or 0) / 512)
    machine_score = _clamp_score((0.35 * cpu_score) + (0.5 * gpu_score) + (0.15 * memory_score))

    return {
        "cpu_model": cpu_model,
        "cpu_physical_cores": physical,
        "cpu_logical_cores": logical,
        "cpu_max_clock_mhz": None,
        "memory_total_mb": memory_total_mb,
        "gpu_vram_mb": gpu_vram_mb,
        "cpu_score": cpu_score,
        "gpu_score": gpu_score,
        "memory_score": memory_score,
        "machine_score": machine_score,
        "ranking_version": "v1",
    }


def _is_gpu_runtime_unavailable(stderr_or_logs: str) -> bool:
    """Return True when output signals that a Docker GPU runtime is absent."""
    lowered = stderr_or_logs.lower()
    signals = [
        "could not select device driver",
        "capabilities: [[gpu]]",
        "nvidia-container-cli: initialization error",
        "wsl environment detected but no adapters were found",
        "no cuda-capable device",
        "unknown runtime specified nvidia",
        "could not load nvml",
    ]
    return any(s in lowered for s in signals)


def _is_wsl() -> bool:
    """Return True when running inside Windows Subsystem for Linux."""
    if platform.system() != "Linux":
        return False
    try:
        proc_version = Path("/proc/version").read_text(errors="replace").lower()
        return "microsoft" in proc_version or "wsl" in proc_version
    except OSError:
        return False


def _resolve_workspace_root(requested_workspace: str) -> str:
    """Resolve workspace path robustly across Linux/macOS/WSL environments."""
    candidate = Path(requested_workspace)

    # WSL paths under /mnt/* can cause file-system quirks for high-churn temp data.
    # Move default workspace to a Linux-native tmp dir for better reliability.
    resolved = candidate.resolve() if not candidate.is_absolute() else candidate
    if requested_workspace == DEFAULT_WORKSPACE and _is_wsl() and str(resolved).startswith("/mnt/"):
        candidate = Path(tempfile.gettempdir()) / "rvidia-p2p-workspaces"

    if candidate.exists() and not candidate.is_dir():
        candidate = Path(f"{candidate}.dir")

    return str(candidate)


def _safe_mkdir(path: Path) -> None:
    if path.exists() and not path.is_dir():
        path.unlink()
    path.mkdir(parents=True, exist_ok=True)


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _job_dir(workspace_root: str, job_id: str) -> Path:
    return Path(workspace_root).resolve() / job_id


def _job_state_path(workspace_root: str, job_id: str) -> Path:
    return _job_dir(workspace_root, job_id) / "job_state.json"


def _load_job_state(workspace_root: str, job_id: str) -> dict[str, Any]:
    state_path = _job_state_path(workspace_root, job_id)
    if not state_path.exists():
        return {}
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_job_state(workspace_root: str, job_id: str, state: dict[str, Any]) -> None:
    state_path = _job_state_path(workspace_root, job_id)
    _safe_mkdir(state_path.parent)
    enriched = dict(state)
    enriched["job_id"] = job_id
    enriched["updated_at"] = int(time.time())
    state_path.write_text(json.dumps(enriched, indent=2), encoding="utf-8")


# â”€â”€ Docker helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def _run_command_with_logs(command: str | list[str], cwd: Path):
    if isinstance(command, str):
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    else:
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

    captured: list[str] = []

    async def lines():
        if proc.stdout is None:
            return
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            text = raw.decode("utf-8", errors="replace").rstrip("\n")
            captured.append(text)
            yield text

    return proc, lines(), captured


def _docker_container_running(container_name: str) -> bool:
    """Check if a named Docker container is still running."""
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format={{.State.Running}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except Exception:
        return False


def _detect_gvisor() -> bool:
    """Return True if the gVisor 'runsc' runtime is registered with Docker."""
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{json .Runtimes}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            runtimes = json.loads(result.stdout.strip())
            return "runsc" in runtimes
    except Exception:
        pass
    return False


# â”€â”€ iroh helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class _DownloadCallback:
    async def progress(self, _progress):
        return None


def _blobs_from_node(node: RvidiaNode) -> Any:
    owner = node._endpoint_owner
    if owner is None:
        raise RuntimeError("iroh owner/client is unavailable")
    blobs_getter = getattr(owner, "blobs", None)
    if not callable(blobs_getter):
        raise RuntimeError("iroh client does not expose blobs API")
    return blobs_getter()


async def _share_file_ticket(node: RvidiaNode, file_path: Path) -> str:
    blobs: Any = _blobs_from_node(node)
    content = file_path.read_bytes()
    outcome = await blobs.add_bytes_named(content, file_path.name)
    ticket = await blobs.share(outcome.hash, iroh.BlobFormat.RAW, iroh.AddrInfoOptions.RELAY_AND_ADDRESSES)
    return str(ticket)


async def _download_ticket_to_path(node: RvidiaNode, ticket_str: str, output_path: Path) -> Path:
    blobs: Any = _blobs_from_node(node)
    ticket = iroh.BlobTicket(ticket_str)
    await blobs.download(ticket.hash(), ticket.as_download_options(), _DownloadCallback())

    # Ensure destination directory exists and use absolute path (fixes IrohError).
    abs_output_path = Path(output_path).resolve()
    _safe_mkdir(abs_output_path.parent)
    print(f"[RVIDIA] Writing artifact to: {abs_output_path}")

    if abs_output_path.exists():
        abs_output_path.unlink()

    try:
        await blobs.write_to_path(ticket.hash(), str(abs_output_path))
        return abs_output_path
    except Exception as primary_error:
        # Log detailed diagnostics to aid debugging IrohError.
        import stat as _stat
        parent = abs_output_path.parent
        try:
            mode = oct(_stat.S_IMODE(parent.stat().st_mode))
        except Exception:
            mode = "unknown"
        print(
            f"[RVIDIA] IrohError writing to '{abs_output_path}'. "
            f"Parent dir '{parent}' permissions: {mode}. "
            f"Platform: {platform.system()}. WSL: {_is_wsl()}.",
            file=sys.stderr,
        )

        # Strategy 2: write to a Linux-native temp dir, then copy to requested destination.
        # This avoids iroh FFI failures on /mnt/c/... paths in WSL.
        tmp_dir = Path(tempfile.gettempdir()) / "rvidia-iroh" / str(uuid.uuid4())
        _safe_mkdir(tmp_dir)
        tmp_path = tmp_dir / (abs_output_path.name or "artifact.bin")

        try:
            await blobs.write_to_path(ticket.hash(), str(tmp_path))
        except Exception as tmp_error:
            raise RuntimeError(
                f"Failed to write downloaded ticket to '{abs_output_path}' (primary) "
                f"and to temp path '{tmp_path}': {primary_error} | {tmp_error}"
            ) from tmp_error

        # Copy from temp to the requested destination.
        _safe_mkdir(abs_output_path.parent)
        try:
            shutil.copy2(str(tmp_path), str(abs_output_path))
            print(f"[RVIDIA] Artifact copied from temp '{tmp_path}' to '{abs_output_path}'.")
            return abs_output_path
        except Exception as copy_error:
            # Keep the temp artifact so the user can recover it manually.
            raise RuntimeError(
                f"Wrote artifact to temp path '{tmp_path}' but could not copy to "
                f"'{abs_output_path}': {copy_error}. Recover manually from temp path."
            ) from copy_error


# â”€â”€ Signaling â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _push_signal(
    api_base: str,
    token: str,
    job_id: str,
    from_node_id: str,
    to_node_id: str,
    message: dict[str, Any],
) -> None:
    _api_post(
        api_base,
        f"/p2p/jobs/{job_id}/offer",
        token,
        {
            "from_node_id": from_node_id,
            "to_node_id": to_node_id,
            "offer": json.dumps(message),
        },
    )


def _pull_signals(api_base: str, token: str, job_id: str, node_id: str) -> list[dict[str, Any]]:
    payload = _api_get(api_base, f"/p2p/jobs/{job_id}/signals?node_id={node_id}", token)
    signals = payload.get("signals", [])
    parsed: list[dict[str, Any]] = []
    for signal in signals:
        raw_offer = signal.get("offer")
        if not isinstance(raw_offer, str):
            continue
        try:
            parsed_offer = json.loads(raw_offer)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed_offer, dict):
            continue
        parsed_offer["from_node_id"] = signal.get("from_node_id")
        parsed_offer["to_node_id"] = signal.get("to_node_id")
        parsed.append(parsed_offer)
    return parsed


# â”€â”€ Host logic â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def _share_artifacts_and_build_result_message(
    node: RvidiaNode,
    output_files: list[Path],
    logs_file: Path,
    success: bool,
    error_message: str | None,
    transfer_id: str | None = None,
) -> dict[str, Any]:
    artifact_tickets: list[dict[str, str]] = []
    for out_file in output_files:
        ticket_str = await _share_file_ticket(node, out_file)
        artifact_tickets.append(
            {
                "name": out_file.name,
                "ticket": ticket_str,
                "sha256": _sha256_file(out_file),
            }
        )

    logs_ticket = await _share_file_ticket(node, logs_file)
    return {
        "type": "result_ticket",
        "transfer_id": transfer_id or str(uuid.uuid4()),
        "success": success,
        "artifact_tickets": artifact_tickets,
        "artifact_ticket": artifact_tickets[0]["ticket"] if artifact_tickets else "",
        "artifact_name": artifact_tickets[0]["name"] if artifact_tickets else "",
        "logs_ticket": logs_ticket,
        "error_message": error_message,
    }


async def _wait_for_result_ack(
    api_base: str,
    token: str,
    job_id: str,
    node_id: str,
    transfer_id: str,
    timeout_seconds: int,
) -> bool:
    started = time.time()
    while (time.time() - started) < timeout_seconds:
        for signal in _pull_signals(api_base, token, job_id, node_id):
            if signal.get("type") == "result_ack" and signal.get("transfer_id") == transfer_id:
                return True
        await asyncio.sleep(_ACK_POLL_INTERVAL)
    return False


async def _delivery_polling_loop(
    args,
    node_id: str,
    result_message: dict[str, Any],
    initial_receiver_node_id: str | None = None,
) -> tuple[bool, str | None]:
    started = time.time()
    last_receiver = initial_receiver_node_id or None

    while (time.time() - started) < _DELIVERY_TIMEOUT_SECONDS:
        peers = _api_get(args.api_base, f"/p2p/jobs/{args.job_id}/peers", args.token)
        latest_receiver = str(peers.get("latest_receiver_node_id") or peers.get("receiver_node_id") or "").strip()
        if latest_receiver:
            last_receiver = latest_receiver

        if not last_receiver:
            print("[RVIDIA] Waiting for receiver re-registration...")
            await asyncio.sleep(_RESULT_RETRY_INTERVAL)
            continue

        try:
            _push_signal(
                api_base=args.api_base,
                token=args.token,
                job_id=args.job_id,
                from_node_id=node_id,
                to_node_id=last_receiver,
                message=result_message,
            )
            print(
                f"[RVIDIA] result_ticket sent to receiver={last_receiver} "
                f"(transfer_id={result_message.get('transfer_id')})"
            )
        except RuntimeError as exc:
            print(f"[RVIDIA] Failed to push result_ticket: {exc}", file=sys.stderr)
            await asyncio.sleep(_RESULT_RETRY_INTERVAL)
            continue

        acked = await _wait_for_result_ack(
            api_base=args.api_base,
            token=args.token,
            job_id=args.job_id,
            node_id=node_id,
            transfer_id=str(result_message.get("transfer_id") or ""),
            timeout_seconds=_RESULT_RETRY_INTERVAL,
        )
        if acked:
            return True, last_receiver

        print("[RVIDIA] No ACK yet, retrying with latest peer state...")

    return False, last_receiver


def _collect_host_artifacts_from_state(state: dict[str, Any]) -> list[Path]:
    raw_artifacts = state.get("artifacts")
    artifacts: list[Any] = raw_artifacts if isinstance(raw_artifacts, list) else []
    paths: list[Path] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        path_value = artifact.get("path")
        if not isinstance(path_value, str) or not path_value:
            continue
        path = Path(path_value)
        if path.exists() and path.is_file():
            paths.append(path)
    return paths


async def _host_execute_docker(
    args,
    node: RvidiaNode,
    node_id: str,
    receiver_node_id: str,
    repo_url: str,
    branch: str,
    docker_args: str,
    prefer_gpu: bool,
) -> dict[str, Any]:
    """Clone repo, execute docker workload, and return local artifact metadata."""
    workspace_dir = Path(args.workspace) / args.job_id
    _safe_mkdir(workspace_dir)

    outputs_dir = workspace_dir / "outputs"
    _safe_mkdir(outputs_dir)

    _api_patch(
        args.api_base,
        f"/p2p/jobs/{args.job_id}/status",
        args.token,
        {"status": "running", "error_message": None},
    )

    # 1. Clone the repository.
    _api_set_checkpoint(
        args.api_base,
        args.token,
        args.job_id,
        "host",
        "cloning_repo",
        {"repo_url": repo_url, "branch": branch},
    )
    repo_dir = workspace_dir / "repo"
    if repo_dir.exists():
        shutil.rmtree(repo_dir)

    print(f"[RVIDIA] Cloning {repo_url} (branch: {branch})...")
    clone_cmd = f"git clone --depth=1 --branch {branch} {repo_url} repo"
    clone_proc, clone_logs, clone_captured = await _run_command_with_logs(clone_cmd, workspace_dir)
    async for line in clone_logs:
        print(f"[git] {line}")
    clone_rc = await clone_proc.wait()
    if clone_rc != 0:
        raise RuntimeError(f"git clone failed (exit {clone_rc}): {' '.join(clone_captured[-5:])}")

    image_tag = f"task_{args.job_id[:12]}"

    # 2. Docker build.
    _api_set_checkpoint(
        args.api_base,
        args.token,
        args.job_id,
        "host",
        "building_image",
        {"image_tag": image_tag},
    )
    print(f"[RVIDIA] Building Docker image '{image_tag}'...")
    build_cmd = f"docker build -t {image_tag} ."
    build_proc, build_logs, build_captured = await _run_command_with_logs(build_cmd, repo_dir)
    async for line in build_logs:
        print(f"[docker build] {line}")
    build_rc = await build_proc.wait()
    if build_rc != 0:
        raise RuntimeError(f"docker build failed (exit {build_rc}): {' '.join(build_captured[-5:])}")

    # 3. Docker run â€” GPU pass-through, /outputs volume, extra docker_args.
    abs_outputs = str(outputs_dir.resolve())

    # Parse extra docker args safely to avoid quoting issues on Windows paths.
    extra_args: list[str] = []
    if docker_args and docker_args.strip():
        try:
            extra_args = shlex.split(docker_args, posix=False)
        except ValueError as exc:
            raise RuntimeError(
                f"Failed to parse --docker-args {docker_args!r}: {exc}. "
                "Hint: check quoting and special characters."
            ) from exc

    # Probe gVisor once â€” result captured by the closure below.
    use_gvisor = _detect_gvisor()
    if use_gvisor:
        print("[RVIDIA] gVisor (runsc) detected; CPU containers will use kernel-level isolation.")

    def _build_run_args(use_gpu: bool) -> list[str]:
        cmd = ["docker", "run", "--rm"]

        # â”€â”€ Runtime selection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # GPU passthrough requires the nvidia runtime and is incompatible with
        # runsc, so gVisor is only applied on CPU-mode containers.
        if use_gpu:
            cmd += ["--gpus", "all"]
        elif use_gvisor:
            cmd += ["--runtime", "runsc"]

        # â”€â”€ Resource throttling (DoS / fork-bomb prevention) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        cmd += [
            "--memory=4g",
            "--cpus=2.0",
            "--pids-limit", "100",
        ]

        # â”€â”€ Privilege stripping â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        cmd += [
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
        ]

        # â”€â”€ Filesystem hardening â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Standard networking is preserved so jobs can fetch external assets.
        cmd += [
            "--read-only",     # immutable root FS
            "--tmpfs", "/tmp", # writable scratch space without host exposure
        ]

        # â”€â”€ Strictly isolated output volume â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # abs_outputs is already resolved to an absolute path above.
        cmd += ["-v", f"{abs_outputs}:/outputs"]

        # Renter-supplied extra args appended last (after all hardening flags).
        cmd += extra_args
        cmd.append(image_tag)
        return cmd

    print(f"[RVIDIA] Running container '{image_tag}'...")
    print(f"[RVIDIA] GPU requested: {prefer_gpu}")
    _api_set_checkpoint(
        args.api_base,
        args.token,
        args.job_id,
        "host",
        "running_container",
        {"image_tag": image_tag, "prefer_gpu": prefer_gpu},
    )
    run_rc = 1
    run_captured: list[str] = []
    execution_mode = "GPU"

    if prefer_gpu:
        # Prefer GPU runtime, but fall back to CPU when Docker GPU runtime is unavailable.
        gpu_first = _build_run_args(use_gpu=True)
        run_proc, run_logs, run_captured = await _run_command_with_logs(gpu_first, workspace_dir)
        async for line in run_logs:
            print(f"[docker run] {line}")
        run_rc = await run_proc.wait()
    else:
        print("[RVIDIA] No GPU detected; running container in CPU mode.")
        cpu_cmd = _build_run_args(use_gpu=False)
        run_proc, run_logs, run_captured = await _run_command_with_logs(cpu_cmd, workspace_dir)
        async for line in run_logs:
            print(f"[docker run] {line}")
        run_rc = await run_proc.wait()

    if run_rc != 0:
        combined = "\n".join(run_captured).lower()
        gpu_error_markers = [
            "could not select device driver",
            "capabilities: [[gpu]]",
            "nvidia-container-cli",
            "wsl environment detected but no adapters were found",
            "error running prestart hook",
            "failed to create shim task",
        ]
        gpu_unavailable = any(marker in combined for marker in gpu_error_markers)
        if gpu_unavailable:
            print("[RVIDIA] Docker GPU runtime unavailable; retrying container without GPU flags.")
            cpu_fallback = _build_run_args(use_gpu=False)
            cpu_proc, cpu_logs, cpu_captured = await _run_command_with_logs(cpu_fallback, workspace_dir)
            async for line in cpu_logs:
                print(f"[docker run] {line}")
            run_rc = await cpu_proc.wait()
            run_captured.extend(["", "[CPU FALLBACK]"] + cpu_captured)
            execution_mode = "CPU fallback"

    print(f"[RVIDIA] Execution mode: {execution_mode}")

    # 4. Write execution log.
    logs_file = workspace_dir / "execution.log"
    logs_file.write_text(
        "\n".join(run_captured) or f"Container exited with code {run_rc}",
        encoding="utf-8",
    )

    # 5. Collect all files from outputs/, plus the log.
    output_files: list[Path] = [f for f in outputs_dir.rglob("*") if f.is_file()]
    if not output_files:
        # Fall back: write stdout to an artifact so receiver always gets something.
        fallback = outputs_dir / "artifact.txt"
        fallback.write_text(
            "\n".join(run_captured) or f"Container exited with code {run_rc}",
            encoding="utf-8",
        )
        output_files = [fallback]

    print(f"[RVIDIA] Collected {len(output_files)} output file(s)")
    for out_file in output_files:
        size = out_file.stat().st_size
        print(f"[RVIDIA]   {out_file.name} ({size} bytes)")

    success = run_rc == 0
    _api_set_checkpoint(
        args.api_base,
        args.token,
        args.job_id,
        "host",
        "artifact_ready",
        {"artifact_count": len(output_files), "success": success},
    )
    return {
        "success": success,
        "error_message": None if success else f"Container exited with code {run_rc}",
        "run_rc": run_rc,
        "receiver_node_id": receiver_node_id,
        "output_files": [str(path.resolve()) for path in output_files],
        "logs_file": str(logs_file.resolve()),
    }


async def _host_delivery_from_state(args, node: RvidiaNode, node_id: str, state: dict[str, Any]) -> bool:
    output_files = _collect_host_artifacts_from_state(state)
    logs_file = Path(str(state.get("logs_file") or "")).resolve()
    if not logs_file.exists():
        raise RuntimeError(f"Cannot resume delivery: missing logs file at '{logs_file}'")
    if not output_files:
        raise RuntimeError("Cannot resume delivery: no artifact files found in persisted state")

    success = bool(state.get("success"))
    error_message = str(state.get("error_message")) if state.get("error_message") else None
    transfer_id = str(state.get("transfer_id") or str(uuid.uuid4()))
    result_message = await _share_artifacts_and_build_result_message(
        node=node,
        output_files=output_files,
        logs_file=logs_file,
        success=success,
        error_message=error_message,
        transfer_id=transfer_id,
    )
    state["transfer_id"] = str(result_message.get("transfer_id") or transfer_id)
    _save_job_state(args.workspace, args.job_id, state)

    acked, receiver_node_id = await _delivery_polling_loop(
        args=args,
        node_id=node_id,
        result_message=result_message,
        initial_receiver_node_id=state.get("receiver_node_id"),
    )
    if receiver_node_id:
        state["receiver_node_id"] = receiver_node_id
        _save_job_state(args.workspace, args.job_id, state)
    return acked


async def run_host(args):
    args.job_id = _resolve_requested_job_id(args.api_base, args.token, args.job_id)
    resolved_workspace = _resolve_workspace_root(args.workspace)
    if resolved_workspace != args.workspace:
        print(f"[RVIDIA] Workspace path adjusted to: {resolved_workspace}")
    args.workspace = resolved_workspace

    workspace = WorkspaceManager(args.workspace)
    node = RvidiaNode(workspace)
    node_id = await node.initialize(secret_key=args.secret_key)

    gpu_info = _detect_gpu()
    machine_profile = _build_machine_profile(gpu_info)
    print(f"[RVIDIA] GPU: {gpu_info.get('gpu_model') or 'not detected'}")

    legacy_access_mode = False
    try:
        state = _get_access_state(args.api_base, args.token, args.job_id)
    except RuntimeError as exc:
        details = str(exc)
        if '"detail":"Not Found"' in details or '"detail": "Not Found"' in details:
            legacy_access_mode = True
            state = {}
            print(
                "[RVIDIA] Access-handshake endpoints are unavailable on target backend; using legacy host flow.",
                file=sys.stderr,
            )
        elif "API error 404" in details:
            raise RuntimeError(_job_not_found_hint(args.api_base, args.token, args.job_id)) from exc
        else:
            raise

    if (not legacy_access_mode) and (not bool(state.get("is_owner"))):
        if bool(args.request_access) and str(state.get("access_status") or "") == "open":
            _api_post(args.api_base, f"/p2p/jobs/{args.job_id}/request-access", args.token, {})
            print("[RVIDIA] Access requested; waiting for owner acceptance...")
        await _wait_for_access_accepted(args.api_base, args.token, args.job_id)

    try:
        _api_post(
            args.api_base,
            f"/p2p/jobs/{args.job_id}/register-host",
            args.token,
            {"node_id": node_id, **gpu_info, **machine_profile},
        )
    except RuntimeError as exc:
        if "Job not found" in str(exc):
            raise RuntimeError(
                f"Job '{args.job_id}' was not found on {args.api_base}. "
                "Use the job ID from the same backend environment and account token."
            ) from exc
        raise

    print(f"HOST_NODE_ID={node_id}")
    _api_set_checkpoint(args.api_base, args.token, args.job_id, "host", "registered", {"node_id": node_id})
    heartbeat_task = asyncio.create_task(_heartbeat_loop(args, "host", node_id))

    try:
        persisted_state = _load_job_state(args.workspace, args.job_id)
        if not isinstance(persisted_state, dict):
            persisted_state = {}

        if persisted_state.get("phase") == "artifact_ready":
            print("[RVIDIA] Resuming host delivery from persisted state (artifact already computed).")
            _api_set_artifact_state(args.api_base, args.token, args.job_id, "READY_FOR_TRANSFER")
            _api_set_checkpoint(args.api_base, args.token, args.job_id, "host", "resume_artifact_ready")
        else:
            print("[RVIDIA] Host waiting for renter repo signal...")
            _api_set_checkpoint(args.api_base, args.token, args.job_id, "host", "waiting_input_ticket")
            incoming: dict[str, Any] | None = None
            waited = 0
            while incoming is None:
                for signal in _pull_signals(args.api_base, args.token, args.job_id, node_id):
                    if signal.get("type") == "input_ticket":
                        incoming = signal
                        break
                if incoming is None:
                    await asyncio.sleep(2)
                    waited += 2
                    if waited % 20 == 0:
                        print(
                            f"[RVIDIA] Still waiting for renter input_ticket on job {args.job_id} "
                            f"({waited}s elapsed).",
                        )

            receiver_node_id = str(incoming.get("from_node_id") or "")
            repo_url = str(incoming.get("repo_url") or "")
            branch = str(incoming.get("branch") or "main")
            docker_args = str(incoming.get("docker_args") or "")

            if not receiver_node_id or not repo_url:
                raise RuntimeError("Invalid input_ticket signal: missing receiver_node_id or repo_url")

            _api_set_checkpoint(
                args.api_base,
                args.token,
                args.job_id,
                "host",
                "input_ticket_received",
                {"receiver_node_id": receiver_node_id, "repo_url": repo_url, "branch": branch},
            )

            computed = await _host_execute_docker(
                args=args,
                node=node,
                node_id=node_id,
                receiver_node_id=receiver_node_id,
                repo_url=repo_url,
                branch=branch,
                docker_args=docker_args,
                prefer_gpu=bool(gpu_info.get("gpu_model")),
            )

            artifacts = []
            for output_path in computed["output_files"]:
                artifact_path = Path(str(output_path)).resolve()
                if artifact_path.exists() and artifact_path.is_file():
                    artifacts.append(
                        {
                            "name": artifact_path.name,
                            "path": str(artifact_path),
                            "size": artifact_path.stat().st_size,
                            "sha256": _sha256_file(artifact_path),
                        }
                    )

            persisted_state = {
                "phase": "artifact_ready",
                "receiver_node_id": computed.get("receiver_node_id"),
                "repo_url": repo_url,
                "branch": branch,
                "docker_args": docker_args,
                "success": bool(computed.get("success")),
                "error_message": computed.get("error_message"),
                "logs_file": computed.get("logs_file"),
                "artifacts": artifacts,
            }
            _save_job_state(args.workspace, args.job_id, persisted_state)
            _api_set_artifact_state(args.api_base, args.token, args.job_id, "READY_FOR_TRANSFER")

        _api_set_checkpoint(args.api_base, args.token, args.job_id, "host", "delivering")
        delivered = await _host_delivery_from_state(args, node, node_id, persisted_state)
        if not delivered:
            raise RuntimeError("Artifact delivery timed out without receiver ACK")
        _api_set_checkpoint(args.api_base, args.token, args.job_id, "host", "artifact_delivered")

        persisted_state["phase"] = "delivered"
        _save_job_state(args.workspace, args.job_id, persisted_state)
        _api_set_artifact_state(args.api_base, args.token, args.job_id, "DELIVERED")

        output_files = _collect_host_artifacts_from_state(persisted_state)
        _api_post(
            args.api_base,
            f"/p2p/jobs/{args.job_id}/complete",
            args.token,
            {
                "success": bool(persisted_state.get("success")),
                "artifact_name": output_files[0].name if output_files else None,
                "artifact_path": str(output_files[0]) if output_files else None,
                "error_message": persisted_state.get("error_message"),
            },
        )
        _api_set_checkpoint(args.api_base, args.token, args.job_id, "host", "completed")
        print(f"[RVIDIA] Host completed task {args.job_id}.")
    finally:
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task


async def _resolve_host_node_id(api_base: str, token: str, job_id: str, preferred: str = "") -> str:
    host_node_id = preferred.strip()
    while not host_node_id:
        peers = _api_get(api_base, f"/p2p/jobs/{job_id}/peers", token)
        host_node_id = str(peers.get("latest_host_node_id") or peers.get("host_node_id") or "").strip()
        if not host_node_id:
            print("[RVIDIA] Waiting for host registration...")
            await asyncio.sleep(2)
    return host_node_id


async def _receive_and_ack_result(args, node: RvidiaNode, node_id: str) -> tuple[list[Path], bool, str | None]:
    result: dict[str, Any] | None = None
    stalled_polls = 0
    _api_set_checkpoint(args.api_base, args.token, args.job_id, "receiver", "waiting_result_ticket")
    while result is None:
        for signal in _pull_signals(args.api_base, args.token, args.job_id, node_id):
            if signal.get("type") == "result_ticket":
                result = signal
                break
        if result is None:
            await asyncio.sleep(2)
            stalled_polls += 1
            if stalled_polls % 5 == 0:
                peers = _api_get(args.api_base, f"/p2p/jobs/{args.job_id}/peers", args.token)
                status = str(peers.get("status") or "")
                if status in {"queued", "failed"} and not peers.get("host_node_id"):
                    raise RuntimeError(
                        "Host session appears stale and job has been re-queued. "
                        "Start receiver again after a host re-registers."
                    )

    _api_set_checkpoint(
        args.api_base,
        args.token,
        args.job_id,
        "receiver",
        "result_ticket_received",
        {"from_node_id": str(result.get("from_node_id") or "")},
    )

    transfer_id = str(result.get("transfer_id") or "")
    logs_ticket = str(result.get("logs_ticket") or "")
    success = bool(result.get("success"))

    output_dir = Path(args.output_dir).resolve()
    _safe_mkdir(output_dir)

    artifact_tickets: list[dict] = result.get("artifact_tickets") or []
    if not artifact_tickets and result.get("artifact_ticket"):
        artifact_tickets = [
            {
                "name": str(result.get("artifact_name") or "artifact.txt"),
                "ticket": str(result["artifact_ticket"]),
            }
        ]

    if not artifact_tickets:
        raise RuntimeError(
            f"result_ticket received but contains no artifact tickets "
            f"(transfer_id={transfer_id or 'unknown'})"
        )

    saved_paths: list[Path] = []
    for entry in artifact_tickets:
        ticket_str = str(entry.get("ticket") or "").strip()
        name = str(entry.get("name") or "artifact.bin")
        expected_sha = str(entry.get("sha256") or "").strip().lower()
        if not ticket_str:
            continue
        target_path = await _download_ticket_to_path(node, ticket_str, output_dir / name)
        actual_sha = _sha256_file(target_path).lower()
        if expected_sha and actual_sha != expected_sha:
            raise RuntimeError(
                f"Checksum mismatch for '{name}': expected {expected_sha}, got {actual_sha}"
            )
        saved_paths.append(target_path)

    _api_set_checkpoint(
        args.api_base,
        args.token,
        args.job_id,
        "receiver",
        "artifact_downloaded",
        {"artifact_count": len(saved_paths)},
    )

    if logs_ticket:
        try:
            logs_path = await _download_ticket_to_path(node, logs_ticket, output_dir / "execution.log")
            for line in logs_path.read_text(encoding="utf-8", errors="replace").splitlines():
                print(f"Remote GPU > {line}")
        except Exception as exc:
            print(f"[RVIDIA] Failed to fetch execution log: {exc}", file=sys.stderr)

    sender_host_node = str(result.get("from_node_id") or "")
    if transfer_id and sender_host_node:
        _push_signal(
            api_base=args.api_base,
            token=args.token,
            job_id=args.job_id,
            from_node_id=node_id,
            to_node_id=sender_host_node,
            message={
                "type": "result_ack",
                "transfer_id": transfer_id,
                "job_id": args.job_id,
                "status": "received",
            },
        )

    return saved_paths, success, str(result.get("error_message") or "")


async def _run_receiver_common(args, send_input_ticket: bool) -> None:
    args.job_id = _resolve_requested_job_id(args.api_base, args.token, args.job_id)
    try:
        _get_access_state(args.api_base, args.token, args.job_id)
    except RuntimeError as exc:
        if "API error 404" in str(exc):
            raise RuntimeError(_job_not_found_hint(args.api_base, args.token, args.job_id)) from exc
        raise

    resolved_workspace = _resolve_workspace_root(args.workspace)
    if resolved_workspace != args.workspace:
        print(f"[RVIDIA] Workspace path adjusted to: {resolved_workspace}")
    args.workspace = resolved_workspace

    workspace = WorkspaceManager(args.workspace)
    node = RvidiaNode(workspace)
    node_id = await node.initialize(secret_key=args.secret_key)

    register_receiver_supported = True
    try:
        _api_post(
            args.api_base,
            f"/p2p/jobs/{args.job_id}/register-receiver",
            args.token,
            {"node_id": node_id},
        )
    except RuntimeError as exc:
        details = str(exc)
        if "Access must be accepted" in details:
            raise RuntimeError(
                "Receiver cannot start yet: access is not accepted. "
                "Owner must run accept-access first."
            ) from exc
        if 'API error 404: {"detail":"Job not found"}' in details or 'API error 404: {"detail": "Job not found"}' in details:
            register_receiver_supported = False
            print(
                "[RVIDIA] register-receiver returned 404 for this token/job on server. "
                "Continuing in legacy compatibility mode without receiver registration.",
                file=sys.stderr,
            )
        else:
            raise

    print(f"RECEIVER_NODE_ID={node_id}")
    _api_set_checkpoint(args.api_base, args.token, args.job_id, "receiver", "registered", {"node_id": node_id})
    heartbeat_task = asyncio.create_task(_heartbeat_loop(args, "receiver", node_id))
    host_node_id = await _resolve_host_node_id(args.api_base, args.token, args.job_id, args.host_node_id)

    try:
        if send_input_ticket:
            _api_patch(
                args.api_base,
                f"/p2p/jobs/{args.job_id}/status",
                args.token,
                {"status": "transferring", "error_message": None},
            )
            _push_signal(
                api_base=args.api_base,
                token=args.token,
                job_id=args.job_id,
                from_node_id=node_id,
                to_node_id=host_node_id,
                message={
                    "type": "input_ticket",
                    "repo_url": args.repo_url,
                    "branch": args.branch,
                    "docker_args": getattr(args, "docker_args", "") or "",
                },
            )
            print(f"[RVIDIA] Sent repo signal to host: {args.repo_url} (branch: {args.branch})")
            _api_set_checkpoint(
                args.api_base,
                args.token,
                args.job_id,
                "receiver",
                "input_ticket_sent",
                {"host_node_id": host_node_id, "repo_url": args.repo_url, "branch": args.branch},
            )

        saved_paths, success, error_message = await _receive_and_ack_result(args, node, node_id)
        if register_receiver_supported:
            _api_set_artifact_state(args.api_base, args.token, args.job_id, "DELIVERED")
        _api_post(
            args.api_base,
            f"/p2p/jobs/{args.job_id}/complete",
            args.token,
            {
                "success": success,
                "artifact_name": saved_paths[0].name if saved_paths else None,
                "artifact_path": str(saved_paths[0]) if saved_paths else None,
                "error_message": None if success else error_message or "Remote execution failed",
            },
        )
        _api_set_checkpoint(args.api_base, args.token, args.job_id, "receiver", "completed")
        print(f"[RVIDIA] Receiver completed task {args.job_id}.")
    finally:
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task


async def run_receiver(args):
    await _run_receiver_common(args, send_input_ticket=True)


async def run_resume_host(args):
    args.request_access = False
    await run_host(args)


async def run_resume_receiver(args):
    await _run_receiver_common(args, send_input_ticket=False)


async def run_request_access(args):
    payload = _api_post(args.api_base, f"/p2p/jobs/{args.job_id}/request-access", args.token, {})
    print(json.dumps(payload, indent=2))


async def run_accept_access(args):
    payload = _api_post(args.api_base, f"/p2p/jobs/{args.job_id}/accept-access", args.token, {})
    print(json.dumps(payload, indent=2))


# â”€â”€ CLI parser â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RVIDIA P2P host/receiver CLI")
    subparsers = parser.add_subparsers(dest="role", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--api-base", default=DEFAULT_API_BASE, help="Backend API base URL")
    common.add_argument("--token", required=True, help="Auth bearer token")
    common.add_argument(
        "--job-id",
        required=True,
        help="Job ID from backend (or 'latest'/'auto' to pick newest marketplace job)",
    )
    common.add_argument("--workspace", default=DEFAULT_WORKSPACE, help="Local workspace root")
    common.add_argument("--secret-key", default=None, help="Optional iroh secret key")

    host = subparsers.add_parser("host", parents=[common], help="Start host and execute incoming Docker job")
    host.add_argument(
        "--request-access",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Request access before host registration when job is not owned by this user",
    )
    host.set_defaults(handler=run_host)

    resume_host = subparsers.add_parser("resume-host", parents=[common], help="Resume host from persisted job_state")
    resume_host.set_defaults(handler=run_resume_host)

    receiver = subparsers.add_parser("receiver", parents=[common], help="Submit a GitHub repo job to a remote host")
    receiver.add_argument("--host-node-id", default="", help="Host node ID (optional if host already registered)")
    receiver.add_argument("--repo-url", required=True, help="Public GitHub repository URL (e.g. https://github.com/user/repo)")
    receiver.add_argument("--branch", default="main", help="Branch to clone and build (default: main)")
    receiver.add_argument("--docker-args", default="", help="Extra docker run arguments (e.g. '-e API_KEY=123 -p 8080:8080')")
    receiver.add_argument("--output-dir", default="./outputs", help="Directory to write returned artifacts")
    receiver.set_defaults(handler=run_receiver)

    resume_receiver = subparsers.add_parser(
        "resume-receiver",
        parents=[common],
        help="Resume receiver and re-register a fresh node to recover transfer",
    )
    resume_receiver.add_argument("--host-node-id", default="", help="Host node ID (optional)")
    resume_receiver.add_argument("--output-dir", default="./outputs", help="Directory to write returned artifacts")
    resume_receiver.set_defaults(handler=run_resume_receiver)

    request_access = subparsers.add_parser("request-access", parents=[common], help="Request access to a job")
    request_access.set_defaults(handler=run_request_access)

    accept_access = subparsers.add_parser("accept-access", parents=[common], help="Accept an access request for your job")
    accept_access.set_defaults(handler=run_accept_access)

    return parser


async def _main_async():
    parser = build_parser()
    args = parser.parse_args()
    await args.handler(args)


def main():
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()

