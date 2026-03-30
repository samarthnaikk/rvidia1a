# Rvidia Backend and P2P Documentation

## Overview
This document describes:
- HTTP API endpoints exposed by the FastAPI backend.
- P2P core APIs implemented in backend/app/core/rvidia_core.py.

## HTTP API Endpoints
Base server app setup is in backend/run.py and auth routes are in backend/app/routes/auth.py.

### GET /
- Purpose: health or greeting route.
- Handler file: backend/run.py
- Response:
```json
{
  "message": "Hello from FastAPI 🚀"
}
```

### POST /auth/signup
- Purpose: create a user account.
- Handler file: backend/app/routes/auth.py
- Request body schema: SignupRequest in backend/app/schemas/user.py
```json
{
  "username": "string",
  "email": "user@example.com",
  "password": "string",
  "confirm_password": "string"
}
```
- Validation and behavior:
  - password and confirm_password must match.
  - username or email must be unique.
  - password is stored as password_hash.
- Success response:
```json
{
  "message": "User created successfully"
}
```
- Error responses:
  - 400 Passwords do not match
  - 400 User already exists

### POST /auth/login
- Purpose: authenticate by username or email and return JWT.
- Handler file: backend/app/routes/auth.py
- Request body schema: LoginRequest in backend/app/schemas/user.py
```json
{
  "username_or_email": "string",
  "password": "string"
}
```
- Behavior:
  - Finds user by username or email.
  - Verifies password hash.
  - Returns access token on success.
- Success response:
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```
- Error responses:
  - 400 Invalid credentials

## P2P Core API
Primary implementation file: backend/app/core/rvidia_core.py

### Protocol and transport constants
- ALPN: rvidia/v1 as bytes.
- Framing: 4-byte big-endian length prefix for JSON payloads.
- File transfer chunk size: 64 KB.

### Data class
#### TaskMetadata
Fields:
- command: execution command string.
- filename: source file name.
- task_id: unique task identifier.

### WorkspaceManager
Handles isolated task directories and reconnect-aware cleanup.

#### constructor
WorkspaceManager(base_dir, reconnect_window_seconds=60)
- base_dir: parent path used for task workspaces.
- reconnect_window_seconds: grace period before cleanup after disconnect.

#### create_session(task_id)
- Creates or returns an existing session folder with naming:
  - task_<uuid>
- Returns Path to session directory.

#### mark_disconnected(task_id)
- Starts reconnect grace period timer for an active task.

#### mark_reconnected(task_id)
- Clears reconnect timer when peer reconnects.

#### cleanup(task_id, force=False)
- Deletes task workspace if reconnect grace window has elapsed.
- If force=True, deletes immediately.
- Returns True if directory removed, else False.

#### get_session_dir(task_id)
- Returns current Path for task session if active, else None.

### Framing helper functions

#### send_payload(stream, data)
- Serializes data to JSON bytes.
- Prefixes payload length using 4-byte big-endian header.
- Writes framed bytes to stream.

#### receive_payload(stream)
- Reads 4-byte header, then exact body length.
- Parses JSON and validates object payload.
- Returns dict.

### RvidiaNode
Unified host and renter interface for iroh-backed task exchange.

#### constructor
RvidiaNode(workspace_manager)
- workspace_manager: WorkspaceManager instance.

#### initialize(secret_key=None)
- Creates iroh endpoint using available binding style.
- Supports both Iroh.memory based and Endpoint builder based bindings.
- Returns NodeId string.

#### send_payload(stream, data)
- Convenience wrapper to module-level send_payload.

#### receive_payload(stream)
- Convenience wrapper to module-level receive_payload.

#### transfer_data(stream, path, mode, task_id=None)
Mode send:
- Sends file_start with filename and size.
- Streams file_chunk messages with base64 payload.
- Sends file_end.

Mode receive:
- Expects file_start.
- Resolves destination path.
- Writes chunked data until file_end.
- If task_id provided, destination is routed through WorkspaceManager session.

Returns Path to source file in send mode or destination file in receive mode.

#### send_handshake(stream, command, filename, task_id)
- Sends task_metadata message from renter to host.

#### receive_handshake(stream)
- Reads and validates task_metadata.
- Returns TaskMetadata.

#### stream_logs(stream, log_source)
- Sends log lines as log messages.
- Ends with log_end message.

#### listen_logs(stream)
- Reads log messages and prints each as:
  - Remote GPU > <line>
- Stops on log_end.

#### host_finalize(stream, task_id, success, artifact_path=None)
- Sends task_complete payload.
- If artifact exists, transfers it using transfer_data in send mode.

#### renter_wait_for_finalization(stream, artifact_dir)
- Waits for task_complete.
- If has_artifact is true, receives artifact into artifact_dir.
- Returns tuple: completion payload and optional artifact path.

#### host_prepare_and_receive(stream)
Host workflow helper:
- Receives handshake.
- Creates session workspace.
- Receives renter payload into workspace.
- Returns TaskMetadata and received file path.

#### renter_send_task(stream, command, file_path, task_id)
Renter workflow helper:
- Sends handshake metadata.
- Transfers local file to host.

### Internal stream and endpoint helpers
These are internal utilities used by public APIs.

- _stream_write_all: normalizes write across stream interfaces.
- _stream_read_exact: normalizes exact-read behavior.
- _build_endpoint_kwargs: maps ALPN and secret_key constructor args.
- _normalize_secret_key: normalizes secret key into bytes.
- _create_iroh_endpoint: creates endpoint and keeps owner object when required by binding.

## Typical P2P message sequence
1. Renter sends task_metadata.
2. Renter sends file_start, file_chunk..., file_end.
3. Host streams log..., then log_end.
4. Host sends task_complete.
5. Optional: Host sends artifact as file_start, file_chunk..., file_end.

## Notes
- P2P implementation uses asyncio throughout.
- Workspace isolation is UUID-based per task session.
- Cleanup behavior respects reconnect grace period unless forced.
