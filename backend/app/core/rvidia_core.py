import asyncio
import base64
import inspect
import importlib
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Iterator, Literal
from uuid import uuid4


_FRAME_HEADER_SIZE = 4
_DEFAULT_RECONNECT_WINDOW_SECONDS = 60
_DEFAULT_CHUNK_SIZE = 64 * 1024
_ALPN = b"rvidia/v1"


class WorkspaceManager:
    """Manage isolated task workspaces with reconnect-aware lifecycle controls."""

    def __init__(self, base_dir: str | Path, reconnect_window_seconds: int = _DEFAULT_RECONNECT_WINDOW_SECONDS) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.reconnect_window_seconds = reconnect_window_seconds
        self._sessions: dict[str, Path] = {}
        self._disconnect_deadlines: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, task_id: str) -> Path:
        """Create or return an existing workspace path for a task."""
        async with self._lock:
            existing = self._sessions.get(task_id)
            if existing is not None:
                self._disconnect_deadlines.pop(task_id, None)
                return existing

            session_dir = self.base_dir / f"task_{uuid4()}"
            session_dir.mkdir(parents=True, exist_ok=False)
            self._sessions[task_id] = session_dir
            self._disconnect_deadlines.pop(task_id, None)
            return session_dir

    async def mark_disconnected(self, task_id: str) -> None:
        """Start a reconnect grace period for an active session."""
        async with self._lock:
            if task_id in self._sessions:
                self._disconnect_deadlines[task_id] = time.time() + self.reconnect_window_seconds

    async def mark_reconnected(self, task_id: str) -> None:
        """Cancel reconnect grace period for a session that returned."""
        async with self._lock:
            self._disconnect_deadlines.pop(task_id, None)

    async def cleanup(self, task_id: str, force: bool = False) -> bool:
        """Delete a workspace if grace window has elapsed or force=True.

        Returns True when a directory was removed, False when cleanup is skipped.
        """
        async with self._lock:
            session_dir = self._sessions.get(task_id)
            if session_dir is None:
                return False

            deadline = self._disconnect_deadlines.get(task_id)
            if not force and deadline is not None and deadline > time.time():
                return False

            self._sessions.pop(task_id, None)
            self._disconnect_deadlines.pop(task_id, None)

        if session_dir.exists():
            shutil.rmtree(session_dir)
            return True
        return False

    async def get_session_dir(self, task_id: str) -> Path | None:
        async with self._lock:
            return self._sessions.get(task_id)


async def send_payload(stream: Any, data: dict[str, Any]) -> None:
    """Send a JSON payload using 4-byte big-endian length-prefixed framing."""
    payload = json.dumps(data).encode("utf-8")
    header = len(payload).to_bytes(_FRAME_HEADER_SIZE, byteorder="big", signed=False)
    await _stream_write_all(stream, header + payload)


async def receive_payload(stream: Any) -> dict[str, Any]:
    """Read one framed JSON payload from the stream."""
    header = await _stream_read_exact(stream, _FRAME_HEADER_SIZE)
    if len(header) != _FRAME_HEADER_SIZE:
        raise ConnectionError("incomplete frame header")

    body_length = int.from_bytes(header, byteorder="big", signed=False)
    body = await _stream_read_exact(stream, body_length)
    if len(body) != body_length:
        raise ConnectionError("incomplete frame body")

    decoded = json.loads(body.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("framed payload must decode to a JSON object")
    return decoded


@dataclass(slots=True)
class TaskMetadata:
    command: str
    filename: str
    task_id: str


class RvidiaNode:
    """Unified host/renter node for Rvidia P2P task execution."""

    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        self.workspace_manager = workspace_manager
        self.endpoint: Any | None = None
        self.node_id: Any | None = None
        self.alpn = _ALPN
        self.chunk_size = _DEFAULT_CHUNK_SIZE

    async def initialize(self, secret_key: str | bytes | None = None) -> str:
        """Initialize iroh endpoint and return node identifier."""
        endpoint = await _create_iroh_endpoint(secret_key=secret_key, alpn=self.alpn)
        self.endpoint = endpoint

        node_id_value = None
        for attr in ("node_id", "node_id_str", "id"):
            candidate = getattr(endpoint, attr, None)
            if candidate is None:
                continue
            if callable(candidate):
                candidate_value = candidate()
                node_id_value = await candidate_value if inspect.isawaitable(candidate_value) else candidate_value
            else:
                node_id_value = candidate
            if node_id_value is not None:
                break

        if node_id_value is None:
            raise RuntimeError("iroh endpoint does not expose a node identifier")

        self.node_id = node_id_value
        return str(node_id_value)

    async def send_payload(self, stream: Any, data: dict[str, Any]) -> None:
        await send_payload(stream, data)

    async def receive_payload(self, stream: Any) -> dict[str, Any]:
        return await receive_payload(stream)

    async def transfer_data(
        self,
        stream: Any,
        path: str | Path,
        mode: Literal["send", "receive"],
        task_id: str | None = None,
    ) -> Path:
        """Transfer data over stream in 64KB chunks.

        For receive mode, task_id routes data into workspace-managed directories.
        """
        if mode == "send":
            source = Path(path)
            if not source.exists() or not source.is_file():
                raise FileNotFoundError(f"source file missing: {source}")

            await send_payload(
                stream,
                {
                    "type": "file_start",
                    "filename": source.name,
                    "size": source.stat().st_size,
                },
            )
            with source.open("rb") as handle:
                while True:
                    chunk = handle.read(self.chunk_size)
                    if not chunk:
                        break
                    await send_payload(
                        stream,
                        {
                            "type": "file_chunk",
                            "data": base64.b64encode(chunk).decode("ascii"),
                        },
                    )

            await send_payload(stream, {"type": "file_end"})
            return source

        if mode == "receive":
            start = await receive_payload(stream)
            if start.get("type") != "file_start":
                raise ValueError("expected file_start before file transfer")

            file_name = str(start.get("filename") or Path(path).name)
            destination = await self._resolve_receive_destination(file_name=file_name, path=path, task_id=task_id)
            destination.parent.mkdir(parents=True, exist_ok=True)

            with destination.open("wb") as handle:
                while True:
                    message = await receive_payload(stream)
                    message_type = message.get("type")
                    if message_type == "file_end":
                        break
                    if message_type != "file_chunk":
                        raise ValueError("unexpected message type during transfer")

                    encoded = message.get("data")
                    if not isinstance(encoded, str):
                        raise ValueError("file_chunk message missing data")
                    handle.write(base64.b64decode(encoded.encode("ascii")))

            return destination

        raise ValueError("mode must be either 'send' or 'receive'")

    async def send_handshake(self, stream: Any, command: str, filename: str, task_id: str) -> None:
        """Renter sends task metadata for host-side execution."""
        await send_payload(
            stream,
            {
                "type": "task_metadata",
                "command": command,
                "filename": filename,
                "task_id": task_id,
            },
        )

    async def receive_handshake(self, stream: Any) -> TaskMetadata:
        payload = await receive_payload(stream)
        if payload.get("type") != "task_metadata":
            raise ValueError("expected task_metadata payload")

        command = payload.get("command")
        filename = payload.get("filename")
        task_id = payload.get("task_id")
        if not isinstance(command, str) or not isinstance(filename, str) or not isinstance(task_id, str):
            raise ValueError("invalid task_metadata payload")

        return TaskMetadata(command=command, filename=filename, task_id=task_id)

    async def stream_logs(self, stream: Any, log_source: AsyncIterator[str] | Iterator[str]) -> None:
        """Host-side telemetry: stream log lines into the P2P channel."""
        if hasattr(log_source, "__aiter__"):
            async for line in log_source:  # type: ignore[union-attr]
                await send_payload(stream, {"type": "log", "line": line})
        else:
            for line in log_source:  # type: ignore[assignment]
                await send_payload(stream, {"type": "log", "line": line})

        await send_payload(stream, {"type": "log_end"})

    async def listen_logs(self, stream: Any) -> None:
        """Renter-side telemetry: print host logs with required prefix."""
        while True:
            payload = await receive_payload(stream)
            payload_type = payload.get("type")
            if payload_type == "log_end":
                return
            if payload_type != "log":
                continue

            line = str(payload.get("line", ""))
            print(f"Remote GPU > {line}", flush=True)

    async def host_finalize(
        self,
        stream: Any,
        task_id: str,
        success: bool,
        artifact_path: str | Path | None = None,
    ) -> None:
        """Host signals completion and optionally streams output artifact."""
        has_artifact = artifact_path is not None and Path(artifact_path).exists()
        await send_payload(
            stream,
            {
                "type": "task_complete",
                "task_id": task_id,
                "success": success,
                "has_artifact": has_artifact,
            },
        )

        if has_artifact and artifact_path is not None:
            await self.transfer_data(stream, path=artifact_path, mode="send")

    async def renter_wait_for_finalization(
        self,
        stream: Any,
        artifact_dir: str | Path,
    ) -> tuple[dict[str, Any], Path | None]:
        """Wait for completion signal and optionally receive artifact."""
        completion = await receive_payload(stream)
        if completion.get("type") != "task_complete":
            raise ValueError("expected task_complete payload")

        output_path: Path | None = None
        if bool(completion.get("has_artifact")):
            artifact_base = Path(artifact_dir)
            artifact_base.mkdir(parents=True, exist_ok=True)
            output_path = await self.transfer_data(
                stream,
                path=artifact_base / "artifact.bin",
                mode="receive",
            )

        return completion, output_path

    async def host_prepare_and_receive(
        self,
        stream: Any,
    ) -> tuple[TaskMetadata, Path]:
        """Host workflow: accept metadata, create workspace, ingest payload."""
        task = await self.receive_handshake(stream)
        await self.workspace_manager.create_session(task.task_id)
        received_path = await self.transfer_data(
            stream,
            path=task.filename,
            mode="receive",
            task_id=task.task_id,
        )
        return task, received_path

    async def renter_send_task(
        self,
        stream: Any,
        command: str,
        file_path: str | Path,
        task_id: str,
    ) -> None:
        """Renter workflow: send metadata then stream payload to host."""
        source = Path(file_path)
        await self.send_handshake(stream, command=command, filename=source.name, task_id=task_id)
        await self.transfer_data(stream, path=source, mode="send")

    async def _resolve_receive_destination(self, file_name: str, path: str | Path, task_id: str | None) -> Path:
        if task_id is not None:
            session_dir = await self.workspace_manager.get_session_dir(task_id)
            if session_dir is None:
                session_dir = await self.workspace_manager.create_session(task_id)
            return session_dir / file_name

        destination = Path(path)
        if destination.is_dir() or str(destination).endswith("/"):
            return destination / file_name
        return destination


async def _stream_write_all(stream: Any, data: bytes) -> None:
    if hasattr(stream, "write_all"):
        await stream.write_all(data)
        return

    if hasattr(stream, "write"):
        maybe = stream.write(data)
        if inspect.isawaitable(maybe):
            await maybe
        if hasattr(stream, "drain"):
            maybe_drain = stream.drain()
            if inspect.isawaitable(maybe_drain):
                await maybe_drain
        return

    if hasattr(stream, "send"):
        maybe = stream.send(data)
        if inspect.isawaitable(maybe):
            await maybe
        return

    raise AttributeError("stream does not support writing")


async def _stream_read_exact(stream: Any, size: int) -> bytes:
    if size == 0:
        return b""

    if hasattr(stream, "read_exact"):
        data = await stream.read_exact(size)
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("read_exact must return bytes")
        return bytes(data)

    if hasattr(stream, "readexactly"):
        data = await stream.readexactly(size)
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("readexactly must return bytes")
        return bytes(data)

    if not hasattr(stream, "read"):
        raise AttributeError("stream does not support reading")

    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        piece = stream.read(remaining)
        if inspect.isawaitable(piece):
            piece = await piece
        if not piece:
            raise ConnectionError("stream closed before expected bytes were read")
        if not isinstance(piece, (bytes, bytearray)):
            raise TypeError("read must return bytes")
        chunk = bytes(piece)
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _build_endpoint_kwargs(endpoint_cls: Any, secret_key: str | bytes | None, alpn: bytes) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    try:
        signature = inspect.signature(endpoint_cls)
    except (TypeError, ValueError):
        signature = None

    if signature is not None:
        params = signature.parameters
        if "alpns" in params:
            kwargs["alpns"] = [alpn]
        elif "alpn" in params:
            kwargs["alpn"] = alpn
        if secret_key is not None and "secret_key" in params:
            kwargs["secret_key"] = secret_key
    return kwargs


async def _create_iroh_endpoint(secret_key: str | bytes | None, alpn: bytes) -> Any:
    try:
        iroh = importlib.import_module("iroh")
    except ImportError as exc:
        raise RuntimeError("iroh Python bindings are required for RvidiaNode") from exc

    endpoint_cls = getattr(iroh, "Endpoint", None)
    if endpoint_cls is None:
        raise RuntimeError("iroh bindings do not expose Endpoint")

    builder = getattr(endpoint_cls, "builder", None)
    if callable(builder):
        configured_builder = builder()
        builder_alpns = getattr(configured_builder, "alpns", None)
        builder_alpn = getattr(configured_builder, "alpn", None)
        builder_secret_key = getattr(configured_builder, "secret_key", None)
        builder_bind = getattr(configured_builder, "bind", None)

        if callable(builder_alpns):
            configured_builder = builder_alpns([alpn])
        elif callable(builder_alpn):
            configured_builder = builder_alpn(alpn)
        if secret_key is not None and callable(builder_secret_key):
            configured_builder = builder_secret_key(secret_key)

        if callable(builder_bind):
            bind_result = builder_bind()
            return await bind_result if inspect.isawaitable(bind_result) else bind_result

    kwargs = _build_endpoint_kwargs(endpoint_cls=endpoint_cls, secret_key=secret_key, alpn=alpn)
    endpoint = endpoint_cls(**kwargs)
    if inspect.isawaitable(endpoint):
        endpoint = await endpoint
    return endpoint
