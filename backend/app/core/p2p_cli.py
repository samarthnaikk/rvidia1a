import argparse
import asyncio
import inspect
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error, request

import iroh

from app.core.rvidia_core import RvidiaNode, WorkspaceManager


DEFAULT_API_BASE = "http://157.180.74.2"

_RECONNECT_INTERVAL = 5  # seconds between reconnect attempts


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _normalize_api_base(api_base: str) -> str:
    return api_base.rstrip("/")


def _build_api_url(api_base: str, path: str, with_api_prefix: bool = False) -> str:
    base = _normalize_api_base(api_base)
    if with_api_prefix and not base.endswith("/api"):
        base = f"{base}/api"
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{base}{normalized_path}"


def _api_request(method: str, api_base: str, path: str, token: str, payload: dict | None = None) -> dict:
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


def _api_post(api_base: str, path: str, token: str, payload: dict) -> dict:
    return _api_request("POST", api_base, path, token, payload)


def _api_patch(api_base: str, path: str, token: str, payload: dict) -> dict:
    return _api_request("PATCH", api_base, path, token, payload)


def _api_get(api_base: str, path: str, token: str) -> dict:
    return _api_request("GET", api_base, path, token)


# ── GPU Detection ─────────────────────────────────────────────────────────────

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


# ── Docker helpers ────────────────────────────────────────────────────────────

async def _run_command_with_logs(command: str, cwd: Path):
    proc = await asyncio.create_subprocess_shell(
        command,
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


# ── iroh helpers ──────────────────────────────────────────────────────────────

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
    abs_output_path.parent.mkdir(parents=True, exist_ok=True)

    if abs_output_path.exists():
        abs_output_path.unlink()

    try:
        await blobs.write_to_path(ticket.hash(), str(abs_output_path))
        return abs_output_path
    except Exception as primary_error:
        # Log directory permissions to stderr to aid debugging IrohError.
        parent = abs_output_path.parent
        import stat as _stat
        try:
            mode = oct(_stat.S_IMODE(parent.stat().st_mode))
        except Exception:
            mode = "unknown"
        print(
            f"[RVIDIA] IrohError writing to '{abs_output_path}'. "
            f"Parent dir '{parent}' permissions: {mode}",
            file=sys.stderr,
        )

        fallback_path = abs_output_path.with_name(
            f"{abs_output_path.stem}-{int(time.time())}{abs_output_path.suffix}"
        )
        if fallback_path.exists():
            fallback_path.unlink()
        try:
            await blobs.write_to_path(ticket.hash(), str(fallback_path))
            return fallback_path
        except Exception as fallback_error:
            raise RuntimeError(
                f"Failed to write downloaded ticket to '{abs_output_path}' or fallback '{fallback_path}': "
                f"{primary_error} | {fallback_error}"
            ) from fallback_error


# ── Signaling ─────────────────────────────────────────────────────────────────

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


# ── Host logic ────────────────────────────────────────────────────────────────

async def _host_execute_docker(
    args,
    node: RvidiaNode,
    node_id: str,
    receiver_node_id: str,
    repo_url: str,
    branch: str,
    docker_args: str,
) -> None:
    """Clone repo, docker build+run inside /outputs volume, ship artifacts back."""
    workspace_dir = Path(args.workspace) / args.job_id
    workspace_dir.mkdir(parents=True, exist_ok=True)

    outputs_dir = workspace_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    _api_patch(
        args.api_base,
        f"/p2p/jobs/{args.job_id}/status",
        args.token,
        {"status": "running", "error_message": None},
    )

    # 1. Clone the repository.
    repo_dir = workspace_dir / "repo"
    if repo_dir.exists():
        import shutil
        shutil.rmtree(repo_dir)

    clone_cmd = f"git clone --depth=1 --branch {branch} {repo_url} repo"
    print(f"[RVIDIA] Cloning {repo_url} (branch: {branch})...")
    clone_proc, clone_logs, clone_captured = await _run_command_with_logs(clone_cmd, workspace_dir)
    async for line in clone_logs:
        print(f"[git] {line}")
    clone_rc = await clone_proc.wait()
    if clone_rc != 0:
        raise RuntimeError(f"git clone failed (exit {clone_rc}): {' '.join(clone_captured[-5:])}")

    image_tag = f"task_{args.job_id[:12]}"

    # 2. Docker build.
    print(f"[RVIDIA] Building Docker image '{image_tag}'...")
    build_cmd = f"docker build -t {image_tag} ."
    build_proc, build_logs, build_captured = await _run_command_with_logs(build_cmd, repo_dir)
    async for line in build_logs:
        print(f"[docker build] {line}")
    build_rc = await build_proc.wait()
    if build_rc != 0:
        raise RuntimeError(f"docker build failed (exit {build_rc}): {' '.join(build_captured[-5:])}")

    # 3. Docker run — GPU pass-through, /outputs volume, extra docker_args.
    abs_outputs = str(outputs_dir.resolve())
    extra = docker_args.strip() if docker_args else ""
    run_cmd = (
        f"docker run --rm --gpus all "
        f"-v {abs_outputs}:/outputs "
        f"{extra} "
        f"{image_tag}"
    ).strip()
    print(f"[RVIDIA] Running container '{image_tag}'...")
    run_proc, run_logs, run_captured = await _run_command_with_logs(run_cmd, workspace_dir)
    async for line in run_logs:
        print(f"[docker run] {line}")
    run_rc = await run_proc.wait()

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

    # 6. Share each output file as an iroh ticket and push signal.
    artifact_tickets: list[dict[str, str]] = []
    for out_file in output_files:
        ticket_str = await _share_file_ticket(node, out_file)
        artifact_tickets.append({"name": out_file.name, "ticket": ticket_str})

    logs_ticket = await _share_file_ticket(node, logs_file)
    success = run_rc == 0

    _push_signal(
        api_base=args.api_base,
        token=args.token,
        job_id=args.job_id,
        from_node_id=node_id,
        to_node_id=receiver_node_id,
        message={
            "type": "result_ticket",
            "success": success,
            "artifact_tickets": artifact_tickets,
            # Legacy single-artifact fields for backwards compat.
            "artifact_ticket": artifact_tickets[0]["ticket"] if artifact_tickets else "",
            "artifact_name": artifact_tickets[0]["name"] if artifact_tickets else "",
            "logs_ticket": logs_ticket,
            "error_message": None if success else f"Container exited with code {run_rc}",
        },
    )

    _api_post(
        args.api_base,
        f"/p2p/jobs/{args.job_id}/complete",
        args.token,
        {
            "success": success,
            "artifact_name": artifact_tickets[0]["name"] if artifact_tickets else None,
            "artifact_path": str(output_files[0]) if output_files else None,
            "error_message": None if success else f"Container exited with code {run_rc}",
        },
    )

    print(f"[RVIDIA] Host execution completed (exit code {run_rc}).")


async def run_host(args):
    workspace = WorkspaceManager(args.workspace)
    node = RvidiaNode(workspace)
    node_id = await node.initialize(secret_key=args.secret_key)

    gpu_info = _detect_gpu()
    print(f"[RVIDIA] GPU: {gpu_info.get('gpu_model') or 'not detected'}")

    _api_post(
        args.api_base,
        f"/p2p/jobs/{args.job_id}/register-host",
        args.token,
        {"node_id": node_id, **gpu_info},
    )
    print(f"HOST_NODE_ID={node_id}")
    print("[RVIDIA] Host waiting for renter repo signal...")

    # Heartbeat/reconnect loop — outer loop retries on network drop.
    running_container: str | None = None

    while True:
        try:
            incoming: dict[str, Any] | None = None
            while incoming is None:
                # Re-attachment: skip if Docker container is still running.
                if running_container and _docker_container_running(running_container):
                    print(f"[RVIDIA] Container '{running_container}' still running, waiting...")
                    await asyncio.sleep(5)
                    continue

                for signal in _pull_signals(args.api_base, args.token, args.job_id, node_id):
                    if signal.get("type") == "input_ticket":
                        incoming = signal
                        break
                if incoming is None:
                    await asyncio.sleep(2)

            receiver_node_id = str(incoming.get("from_node_id") or "")
            repo_url = str(incoming.get("repo_url") or "")
            branch = str(incoming.get("branch") or "main")
            docker_args = str(incoming.get("docker_args") or "")

            if not receiver_node_id or not repo_url:
                raise RuntimeError("Invalid input_ticket signal: missing receiver_node_id or repo_url")

            image_tag = f"task_{args.job_id[:12]}"
            running_container = image_tag

            await _host_execute_docker(
                args=args,
                node=node,
                node_id=node_id,
                receiver_node_id=receiver_node_id,
                repo_url=repo_url,
                branch=branch,
                docker_args=docker_args,
            )
            running_container = None
            break  # Job done — exit loop.

        except (RuntimeError, OSError) as exc:
            print(f"[RVIDIA] Connection/execution error: {exc}. Reconnecting in {_RECONNECT_INTERVAL}s...", file=sys.stderr)
            await asyncio.sleep(_RECONNECT_INTERVAL)


# ── Receiver logic ────────────────────────────────────────────────────────────

async def run_receiver(args):
    workspace = WorkspaceManager(args.workspace)
    node = RvidiaNode(workspace)
    node_id = await node.initialize(secret_key=args.secret_key)

    _api_post(
        args.api_base,
        f"/p2p/jobs/{args.job_id}/register-receiver",
        args.token,
        {"node_id": node_id},
    )
    print(f"RECEIVER_NODE_ID={node_id}")

    host_node_id = args.host_node_id
    while not host_node_id:
        peers = _api_get(args.api_base, f"/p2p/jobs/{args.job_id}/peers", args.token)
        host_node_id = peers.get("host_node_id")
        if not host_node_id:
            print("[RVIDIA] Waiting for host registration...")
            await asyncio.sleep(2)

    if node.endpoint is None:
        raise RuntimeError("iroh endpoint not initialized")

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

    result: dict[str, Any] | None = None
    while result is None:
        for signal in _pull_signals(args.api_base, args.token, args.job_id, node_id):
            if signal.get("type") == "result_ticket":
                result = signal
                break
        if result is None:
            await asyncio.sleep(2)

    logs_ticket = str(result.get("logs_ticket") or "")
    success = bool(result.get("success"))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Download all artifact files.
    artifact_tickets: list[dict] = result.get("artifact_tickets") or []
    if not artifact_tickets and result.get("artifact_ticket"):
        # Legacy single-artifact path.
        artifact_tickets = [
            {"name": str(result.get("artifact_name") or "artifact.txt"), "ticket": str(result["artifact_ticket"])}
        ]

    saved_paths: list[Path] = []
    for entry in artifact_tickets:
        ticket_str = entry.get("ticket", "")
        name = entry.get("name", "artifact.bin")
        if ticket_str:
            path = await _download_ticket_to_path(node, ticket_str, output_dir / name)
            saved_paths.append(path)
            print(f"[RVIDIA] Artifact saved: {path}")

    if logs_ticket:
        logs_path = await _download_ticket_to_path(node, logs_ticket, output_dir / "execution.log")
        for line in logs_path.read_text(encoding="utf-8", errors="replace").splitlines():
            print(f"Remote GPU > {line}")

    _api_post(
        args.api_base,
        f"/p2p/jobs/{args.job_id}/complete",
        args.token,
        {
            "success": success,
            "artifact_name": saved_paths[0].name if saved_paths else None,
            "artifact_path": str(saved_paths[0]) if saved_paths else None,
            "error_message": None if success else str(result.get("error_message") or "Remote execution failed"),
        },
    )

    print(f"[RVIDIA] Receiver completed task {args.job_id}.")


# ── CLI parser ────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RVIDIA P2P host/receiver CLI")
    subparsers = parser.add_subparsers(dest="role", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--api-base", default=DEFAULT_API_BASE, help="Backend API base URL")
    common.add_argument("--token", required=True, help="Auth bearer token")
    common.add_argument("--job-id", required=True, help="Job ID from backend")
    common.add_argument("--workspace", default="./.p2p-workspaces", help="Local workspace root")
    common.add_argument("--secret-key", default=None, help="Optional iroh secret key")

    host = subparsers.add_parser("host", parents=[common], help="Start host and execute incoming Docker job")
    host.set_defaults(handler=run_host)

    receiver = subparsers.add_parser("receiver", parents=[common], help="Submit a GitHub repo job to a remote host")
    receiver.add_argument("--host-node-id", default="", help="Host node ID (optional if host already registered)")
    receiver.add_argument("--repo-url", required=True, help="Public GitHub repository URL (e.g. https://github.com/user/repo)")
    receiver.add_argument("--branch", default="main", help="Branch to clone and build (default: main)")
    receiver.add_argument("--docker-args", default="", help="Extra docker run arguments (e.g. '-e API_KEY=123 -p 8080:8080')")
    receiver.add_argument("--output-dir", default="./outputs", help="Directory to write returned artifacts")
    receiver.set_defaults(handler=run_receiver)

    return parser


async def _main_async():
    parser = build_parser()
    args = parser.parse_args()
    await args.handler(args)


def main():
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
