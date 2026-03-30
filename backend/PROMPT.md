# Task: RVIDIA P2P Evolution – Docker Sandbox, Secure Handshake, and CLI Update

## 1. Context & Reference

- **Documentation:** Refer to `documentation.md` for `RvidiaNode`, `WorkspaceManager`, and `iroh` framing.
- **Style:** Professional, type-hinted, atomic commits (`feat: single line change`).
- **The Shift:** Move from "Local File Transfer" to "Remote GitHub Execution" inside a Docker Sandbox.

## 2. Updated CLI Signature (Renter/Receiver)

Modify the `argparse` in `backend/app/core/p2p_cli.py` for the `receiver` (Renter).

- **Remove:** `--file-path` and `--command`.
- **Add:**
  - `--repo-url`: The public GitHub repository (e.g., `https://github.com/user/repo`).
  - `--branch`: Default to `main`.
  - `--docker-args`: (Optional) String for environment variables or ports (e.g., `-e API_KEY=123`).
- **New Example Command:** `python -m app.core.p2p_cli receiver --api-base ... --token ... --job-id ... --repo-url "https://github.com/user/gpu-app" --branch "main"`

## 3. Docker Sandbox & Execution (The "Divider")

Update `RvidiaNode` host-side logic in `backend/app/core/rvidia_core.py`:

1.  **Isolation:** All code **must** run in a Docker container.
2.  **Lifecycle:** \* Host pulls `TaskMetadata` (now containing `repo_url`).
    - Host clones the repo into a workspace provided by `WorkspaceManager`.
    - Host runs `docker build -t task_<id> .`
    - Host runs `docker run --rm --gpus all -v <local_workspace>/outputs:/outputs task_<id>`.
3.  **Artifact Return:** The Host must monitor the local `outputs/` folder. Once the container exits, every file in that folder must be sent back to the Renter using `transfer_data(mode='send')`.

## 4. Bilateral Marketplace Handshake

Modify the backend logic to ensure users don't just "grab" jobs:

- **Visibility:** \* `GET /p2p/hosts`: Returns available hosts with **GPU Metadata** (Model name, VRAM, Driver version).
  - `GET /p2p/jobs`: Returns pending jobs with **Repo Size/Metadata**.
- **Consent Flow:** 1. User A sends `POST /p2p/jobs/{id}/request-access`. 2. User B must `POST /p2p/jobs/{id}/accept-access`. 3. The CLI `connect` string is only generated/revealed **after** both sides have "Accepted."

## 5. Hardware Reporting & Resilience

- **Hardware Detection:** On CLI startup, the Host must run `nvidia-smi` or `pynvml` to detect GPU details and send them to the backend during `register_host`.
- **CLI Heartbeat:** Wrap the signaling/polling loop in a `while True`. If the network drops, the CLI must attempt to reconnect every 5 seconds without killing the running Docker container.
- **Re-attachment:** Upon reconnecting, the CLI should check if the Docker container for that `job_id` is still running before attempting to start a new one.

## 6. Bug Fix: Iroh `write_to_path` Error

**Fix the `iroh.iroh_ffi.IrohError`** during the artifact return:

- In `_download_ticket_to_path` (or `transfer_data` receive mode), you must:
  1.  Ensure the destination directory exists: `pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)`.
  2.  Pass the **absolute path** as a string: `str(pathlib.Path(output_path).resolve())`.
  3.  Add a generic catch-all for `IrohError` that logs the specific directory permissions to `stderr`.

## 7. Development Constraints

- **No Branch Swapping:** Maintain the current branch.
- **Minimal Invention:** Use the existing `TaskMetadata` and `WorkspaceManager` classes; extend them, don't replace them.
- **Security:** Ensure the Docker volume mount is restricted to the `/outputs` folder only.

---
