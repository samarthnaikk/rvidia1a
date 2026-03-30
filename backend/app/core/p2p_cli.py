import argparse
import asyncio
import inspect
import json
from pathlib import Path
from typing import Any
from urllib import error, request

import iroh

from app.core.rvidia_core import RvidiaNode, WorkspaceManager


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _api_request(method: str, api_base: str, path: str, token: str, payload: dict | None = None) -> dict:
    encoded_body = None
    if payload is not None:
        encoded_body = json.dumps(payload).encode("utf-8")

    req = request.Request(
        url=f"{api_base}{path}",
        method=method,
        headers=_auth_headers(token),
        data=encoded_body,
    )

    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read()
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API error {exc.code}: {details}") from exc

    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _api_post(api_base: str, path: str, token: str, payload: dict) -> dict:
    return _api_request("POST", api_base, path, token, payload)


def _api_patch(api_base: str, path: str, token: str, payload: dict) -> dict:
    return _api_request("PATCH", api_base, path, token, payload)


def _api_get(api_base: str, path: str, token: str) -> dict:
    return _api_request("GET", api_base, path, token)


async def _call_any(obj: Any, names: list[str], *args: Any) -> Any:
    for name in names:
        fn = getattr(obj, name, None)
        if not callable(fn):
            continue

        call_variants = [args]
        if len(args) >= 1:
            call_variants.append(args[:1])
        call_variants.append(())

        for variant in call_variants:
            try:
                value = fn(*variant)
                if inspect.isawaitable(value):
                    value = await value
                return value
            except TypeError:
                continue

    available = [name for name in dir(obj) if not name.startswith("_") and callable(getattr(obj, name, None))]
    raise RuntimeError(
        f"No callable method found from: {', '.join(names)}. "
        f"Available callables on {type(obj).__name__}: {', '.join(sorted(available))}"
    )


def _endpoint_variants(endpoint: Any) -> list[Any]:
    variants = [endpoint]
    for attr in ("endpoint", "node"):
        candidate = getattr(endpoint, attr, None)
        if candidate is None:
            continue
        if callable(candidate):
            try:
                candidate = candidate()
            except TypeError:
                continue
        if candidate is not None:
            variants.append(candidate)
    return variants


async def _candidate_to_stream(candidate: Any, role: str) -> Any:
    if candidate is None:
        raise RuntimeError("P2P stream candidate is None")

    if any(hasattr(candidate, attr) for attr in ("read", "read_exact", "readexactly")) and any(
        hasattr(candidate, attr) for attr in ("write", "write_all", "send")
    ):
        return candidate

    method_groups: list[list[str]]
    if role == "host":
        method_groups = [
            ["accept_bi", "accept_stream", "accept_bidirectional", "accept"],
            ["open_bi", "open_stream", "open_bidirectional"],
        ]
    else:
        method_groups = [
            ["open_bi", "open_stream", "open_bidirectional", "connect_bi"],
            ["accept_bi", "accept_stream", "accept_bidirectional", "accept"],
        ]

    for names in method_groups:
        for try_args in ((),):
            try:
                maybe_stream = await _call_any(candidate, names, *try_args)
            except RuntimeError:
                continue
            if maybe_stream is not None:
                return maybe_stream

    for attr in ("stream", "bi_stream", "channel"):
        nested = getattr(candidate, attr, None)
        if nested is not None:
            if callable(nested):
                nested = nested()
                if inspect.isawaitable(nested):
                    nested = await nested
            if nested is not None:
                return nested

    raise RuntimeError(f"Unable to extract usable stream from {type(candidate).__name__}")


async def _accept_stream(endpoint: Any, alpn: bytes) -> Any:
    for variant in _endpoint_variants(endpoint):
        try:
            candidate = await _call_any(
                variant,
                [
                    "accept",
                    "accept_bi",
                    "accept_stream",
                    "accept_bidirectional",
                    "accept_connection",
                    "accept_conn",
                    "incoming",
                    "listen",
                ],
                alpn,
            )
        except RuntimeError:
            continue

        if hasattr(candidate, "__anext__"):
            candidate = await candidate.__anext__()
        elif hasattr(candidate, "__aiter__"):
            async for item in candidate:
                candidate = item
                break

        return await _candidate_to_stream(candidate, role="host")

    raise RuntimeError("Unable to accept iroh stream from endpoint; no compatible accept/listen API found")


def _has_incoming_api(endpoint: Any) -> bool:
    incoming_names = {
        "accept",
        "accept_bi",
        "accept_stream",
        "accept_bidirectional",
        "accept_connection",
        "accept_conn",
        "incoming",
        "listen",
    }
    for variant in _endpoint_variants(endpoint):
        for name in incoming_names:
            if callable(getattr(variant, name, None)):
                return True
    return False


async def _connect_stream(endpoint: Any, node_id: str, alpn: bytes) -> Any:
    for variant in _endpoint_variants(endpoint):
        try:
            candidate = await _call_any(
                variant,
                ["connect", "connect_bi", "open_stream", "open_bidirectional", "dial"],
                node_id,
                alpn,
            )
        except RuntimeError:
            continue

        return await _candidate_to_stream(candidate, role="receiver")

    raise RuntimeError("Unable to connect iroh stream; no compatible connect API found")


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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    await blobs.write_to_path(ticket.hash(), str(output_path))
    return output_path


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


async def run_host(args):
    workspace = WorkspaceManager(args.workspace)
    node = RvidiaNode(workspace)
    node_id = await node.initialize(secret_key=args.secret_key)

    _api_post(
        args.api_base,
        f"/p2p/jobs/{args.job_id}/register-host",
        args.token,
        {"node_id": node_id},
    )
    print(f"HOST_NODE_ID={node_id}")
    print("Host waiting for renter ticket signal...")

    incoming: dict[str, Any] | None = None
    while incoming is None:
        for signal in _pull_signals(args.api_base, args.token, args.job_id, node_id):
            if signal.get("type") == "input_ticket":
                incoming = signal
                break
        if incoming is None:
            await asyncio.sleep(2)

    receiver_node_id = str(incoming.get("from_node_id") or "")
    input_ticket = str(incoming.get("input_ticket") or "")
    input_filename = str(incoming.get("filename") or "input.bin")
    command_template = str(incoming.get("command") or "")

    if not receiver_node_id or not input_ticket or not command_template:
        raise RuntimeError("Invalid input_ticket signal payload")

    _api_patch(
        args.api_base,
        f"/jobs/{args.job_id}/status",
        args.token,
        {"status": "running", "error_message": None},
    )

    workspace_dir = Path(args.workspace) / args.job_id
    workspace_dir.mkdir(parents=True, exist_ok=True)
    received_file = await _download_ticket_to_path(node, input_ticket, workspace_dir / input_filename)

    command = command_template.replace("{input}", received_file.name)
    print(f"Executing command for task {args.job_id}: {command}")
    proc, _log_source, captured_lines = await _run_command_with_logs(command, workspace_dir)
    return_code = await proc.wait()

    output_lines = list(captured_lines)
    if not output_lines:
        output_lines = [
            f"Command produced no stdout/stderr: {command}",
            f"Exit code: {return_code}",
        ]

    artifact = workspace_dir / "artifact.txt"
    artifact.write_text("\n".join(output_lines), encoding="utf-8")

    logs_file = workspace_dir / "execution.log"
    logs_file.write_text("\n".join(output_lines), encoding="utf-8")

    artifact_ticket = await _share_file_ticket(node, artifact)
    logs_ticket = await _share_file_ticket(node, logs_file)

    success = return_code == 0
    _push_signal(
        api_base=args.api_base,
        token=args.token,
        job_id=args.job_id,
        from_node_id=node_id,
        to_node_id=receiver_node_id,
        message={
            "type": "result_ticket",
            "success": success,
            "artifact_ticket": artifact_ticket,
            "artifact_name": artifact.name,
            "logs_ticket": logs_ticket,
            "error_message": None if success else f"Command exited with code {return_code}",
        },
    )

    _api_post(
        args.api_base,
        f"/jobs/{args.job_id}/complete",
        args.token,
        {
            "success": success,
            "artifact_name": artifact.name,
            "artifact_path": str(artifact),
            "error_message": None if success else f"Command exited with code {return_code}",
        },
    )

    print("Host execution completed.")


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
            print("Waiting for host registration...")
            await asyncio.sleep(2)

    if node.endpoint is None:
        raise RuntimeError("iroh endpoint not initialized")

    _api_patch(
        args.api_base,
        f"/jobs/{args.job_id}/status",
        args.token,
        {"status": "transferring", "error_message": None},
    )

    input_path = Path(args.file_path)
    input_ticket = await _share_file_ticket(node, input_path)
    _push_signal(
        api_base=args.api_base,
        token=args.token,
        job_id=args.job_id,
        from_node_id=node_id,
        to_node_id=host_node_id,
        message={
            "type": "input_ticket",
            "input_ticket": input_ticket,
            "filename": input_path.name,
            "command": args.command,
        },
    )

    result: dict[str, Any] | None = None
    while result is None:
        for signal in _pull_signals(args.api_base, args.token, args.job_id, node_id):
            if signal.get("type") == "result_ticket":
                result = signal
                break
        if result is None:
            await asyncio.sleep(2)

    artifact_ticket = str(result.get("artifact_ticket") or "")
    logs_ticket = str(result.get("logs_ticket") or "")
    success = bool(result.get("success"))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    artifact_path: Path | None = None
    if artifact_ticket:
        artifact_name = str(result.get("artifact_name") or "artifact.txt")
        artifact_path = await _download_ticket_to_path(node, artifact_ticket, output_dir / artifact_name)

    if logs_ticket:
        logs_path = await _download_ticket_to_path(node, logs_ticket, output_dir / "execution.log")
        for line in logs_path.read_text(encoding="utf-8", errors="replace").splitlines():
            print(f"Remote GPU > {line}")

    _api_post(
        args.api_base,
        f"/jobs/{args.job_id}/complete",
        args.token,
        {
            "success": success,
            "artifact_name": artifact_path.name if artifact_path else None,
            "artifact_path": str(artifact_path) if artifact_path else None,
            "error_message": None if success else str(result.get("error_message") or "Remote execution failed"),
        },
    )

    print(f"Receiver completed task {args.job_id}.")
    if artifact_path:
        print(f"Artifact saved at: {artifact_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rvidia MVP P2P host/receiver CLI")
    subparsers = parser.add_subparsers(dest="role", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--api-base", default="http://localhost:8000", help="Backend API base URL")
    common.add_argument("--token", required=True, help="Auth bearer token")
    common.add_argument("--job-id", required=True, help="Job ID from backend")
    common.add_argument("--workspace", default="./.p2p-workspaces", help="Local workspace root")
    common.add_argument("--secret-key", default=None, help="Optional iroh secret key")

    host = subparsers.add_parser("host", parents=[common], help="Start host and execute incoming job")
    host.set_defaults(handler=run_host)

    receiver = subparsers.add_parser("receiver", parents=[common], help="Start receiver and send task to host")
    receiver.add_argument("--host-node-id", default="", help="Host node ID (optional if host already registered)")
    receiver.add_argument("--file-path", required=True, help="Path to input file to send via P2P")
    receiver.add_argument("--command", required=True, help="Execution command on host; supports {input} placeholder")
    receiver.add_argument("--output-dir", default="./outputs", help="Directory to write returned artifact")
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
