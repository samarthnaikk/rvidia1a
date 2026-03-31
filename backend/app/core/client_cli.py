import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import urljoin, urlsplit, urlunsplit


DEFAULT_API_BASE = os.getenv("RVIDIA_API_BASE", "http://localhost:8000")
DEFAULT_SESSION_PATH = Path(os.getenv("RVIDIA_CLI_SESSION", "~/.rvidia-cli/session.json")).expanduser()


def _normalize_api_base(api_base: str) -> str:
    normalized = (api_base or "").strip().rstrip("/")
    if not normalized:
        return normalized

    parsed = urlsplit(normalized)
    host = (parsed.hostname or "").lower()
    port = parsed.port

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


def _session_dir() -> Path:
    return DEFAULT_SESSION_PATH.parent


def _load_session() -> dict[str, Any]:
    if not DEFAULT_SESSION_PATH.exists():
        return {}
    try:
        return json.loads(DEFAULT_SESSION_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_session(payload: dict[str, Any]) -> None:
    _session_dir().mkdir(parents=True, exist_ok=True)
    DEFAULT_SESSION_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _clear_session() -> None:
    try:
        if DEFAULT_SESSION_PATH.exists():
            DEFAULT_SESSION_PATH.unlink()
    except OSError:
        pass


def _resolve_api_base(cli_api_base: str | None) -> str:
    if cli_api_base:
        return _normalize_api_base(cli_api_base)
    session = _load_session()
    session_base = str(session.get("api_base") or "").strip()
    if session_base:
        return _normalize_api_base(session_base)
    return _normalize_api_base(DEFAULT_API_BASE)


def _resolve_token(cli_token: str | None) -> str:
    if cli_token:
        return cli_token
    session = _load_session()
    token = str(session.get("access_token") or "").strip()
    if token:
        return token
    raise RuntimeError("Not logged in. Run 'python -m app.core.client_cli login ...' first.")


def _headers(token: str | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _api_request(
    method: str,
    api_base: str,
    path: str,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    def _perform(url: str) -> tuple[str, str, str]:
        current_url = url
        max_redirects = 5

        for _ in range(max_redirects + 1):
            req = request.Request(url=current_url, method=method, headers=_headers(token), data=data)
            try:
                with request.urlopen(req, timeout=30) as response:
                    raw = response.read().decode("utf-8", errors="replace")
                    return raw, response.headers.get("Content-Type", ""), current_url
            except error.HTTPError as exc:
                if exc.code in {301, 302, 303, 307, 308}:
                    location = exc.headers.get("Location")
                    if location:
                        current_url = urljoin(current_url, location)
                        continue
                raise

        raise RuntimeError(f"Too many redirects while calling API URL: {url}")

    url = _build_api_url(api_base, path, with_api_prefix=False)
    used_url = url
    content_type = ""

    try:
        raw, content_type, used_url = _perform(url)
    except error.HTTPError as exc:
        if exc.code == 404:
            fallback_url = _build_api_url(api_base, path, with_api_prefix=True)
            if fallback_url != url:
                try:
                    raw, content_type, used_url = _perform(fallback_url)
                except error.HTTPError as fallback_exc:
                    details = fallback_exc.read().decode("utf-8", errors="replace")
                    try:
                        parsed = json.loads(details) if details else {}
                    except json.JSONDecodeError:
                        parsed = {"detail": details}
                    message = parsed.get("detail") if isinstance(parsed, dict) else details
                    raise RuntimeError(f"API error {fallback_exc.code}: {message}") from fallback_exc
                except error.URLError as fallback_exc:
                    raise RuntimeError(f"API connection error: {fallback_exc.reason}") from fallback_exc
            else:
                details = exc.read().decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(details) if details else {}
                except json.JSONDecodeError:
                    parsed = {"detail": details}
                message = parsed.get("detail") if isinstance(parsed, dict) else details
                raise RuntimeError(f"API error {exc.code}: {message}") from exc
        else:
            details = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(details) if details else {}
            except json.JSONDecodeError:
                parsed = {"detail": details}
            message = parsed.get("detail") if isinstance(parsed, dict) else details
            raise RuntimeError(f"API error {exc.code}: {message}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"API connection error: {exc.reason}") from exc

    if not raw:
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        compact = " ".join(raw.split())
        snippet = compact[:220]
        hint = ""
        if "text/html" in content_type.lower() or raw.lstrip().startswith("<"):
            hint = " Hint: this looks like an HTML page. Check --api-base points to backend (e.g. http://localhost:8000)."
        raise RuntimeError(
            f"API returned non-JSON response from {used_url} (Content-Type: {content_type or 'unknown'}). "
            f"Body preview: {snippet!r}.{hint}"
        ) from exc


def _print(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


def _add_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--api-base", default=None, help="Backend API base URL (defaults to saved session or env)")
    parser.add_argument("--token", default=None, help="Override bearer token (defaults to saved session)")


def cmd_signup(args: argparse.Namespace) -> None:
    api_base = _resolve_api_base(args.api_base)
    confirm_password = args.confirm_password if args.confirm_password is not None else args.password
    payload = {
        "username": args.username,
        "email": args.email,
        "password": args.password,
        "confirm_password": confirm_password,
    }
    _print(_api_request("POST", api_base, "/auth/signup", payload=payload))


def cmd_login(args: argparse.Namespace) -> None:
    api_base = _resolve_api_base(args.api_base)
    payload = {
        "username_or_email": args.username_or_email,
        "password": args.password,
    }
    token_payload = _api_request("POST", api_base, "/auth/login", payload=payload)
    token = token_payload.get("access_token")
    if not token:
        raise RuntimeError("Login succeeded but no access_token was returned")

    session_payload = {
        "api_base": api_base,
        "access_token": token,
    }

    try:
        me = _api_request("GET", api_base, "/auth/me", token=token)
        session_payload["user"] = me
    except RuntimeError:
        pass

    _save_session(session_payload)
    print(f"Logged in. Session saved to {DEFAULT_SESSION_PATH}")


def cmd_logout(args: argparse.Namespace) -> None:
    _ = args
    _clear_session()
    print("Logged out. Local session cleared.")


def cmd_whoami(args: argparse.Namespace) -> None:
    api_base = _resolve_api_base(args.api_base)
    token = _resolve_token(args.token)
    _print(_api_request("GET", api_base, "/auth/me", token=token))


def cmd_create_job(args: argparse.Namespace) -> None:
    api_base = _resolve_api_base(args.api_base)
    token = _resolve_token(args.token)
    payload = {
        "repo_url": args.repo_url,
        "branch": args.branch,
        "command": args.command,
    }
    _print(_api_request("POST", api_base, "/jobs", token=token, payload=payload))


def cmd_list_jobs(args: argparse.Namespace) -> None:
    api_base = _resolve_api_base(args.api_base)
    token = _resolve_token(args.token)
    path = "/jobs/open" if args.open else "/jobs"
    _print(_api_request("GET", api_base, path, token=token))


def cmd_get_job(args: argparse.Namespace) -> None:
    api_base = _resolve_api_base(args.api_base)
    token = _resolve_token(args.token)
    _print(_api_request("GET", api_base, f"/jobs/{args.job_id}", token=token))


def cmd_list_marketplace(args: argparse.Namespace) -> None:
    api_base = _resolve_api_base(args.api_base)
    token = _resolve_token(args.token)
    _print(_api_request("GET", api_base, "/p2p/jobs", token=token))


def cmd_list_hosts(args: argparse.Namespace) -> None:
    api_base = _resolve_api_base(args.api_base)
    token = _resolve_token(args.token)
    _print(_api_request("GET", api_base, "/p2p/hosts", token=token))


def cmd_request_access(args: argparse.Namespace) -> None:
    api_base = _resolve_api_base(args.api_base)
    token = _resolve_token(args.token)
    _print(_api_request("POST", api_base, f"/p2p/jobs/{args.job_id}/request-access", token=token, payload={}))


def cmd_accept_access(args: argparse.Namespace) -> None:
    api_base = _resolve_api_base(args.api_base)
    token = _resolve_token(args.token)
    _print(_api_request("POST", api_base, f"/p2p/jobs/{args.job_id}/accept-access", token=token, payload={}))


def cmd_access_state(args: argparse.Namespace) -> None:
    api_base = _resolve_api_base(args.api_base)
    token = _resolve_token(args.token)
    _print(_api_request("GET", api_base, f"/p2p/jobs/{args.job_id}/access", token=token))


def _run_p2p_subcommand(args: argparse.Namespace, role: str) -> None:
    api_base = _resolve_api_base(args.api_base)
    token = _resolve_token(args.token)

    cmd = [
        sys.executable,
        "-m",
        "app.core.p2p_cli",
        role,
        "--api-base",
        api_base,
        "--token",
        token,
        "--job-id",
        args.job_id,
        "--workspace",
        args.workspace,
    ]

    if args.secret_key:
        cmd += ["--secret-key", args.secret_key]

    if role == "host":
        if args.no_request_access:
            cmd += ["--no-request-access"]
    elif role == "receiver":
        cmd += ["--repo-url", args.repo_url, "--branch", args.branch, "--output-dir", args.output_dir]
        if args.host_node_id:
            cmd += ["--host-node-id", args.host_node_id]
        if args.docker_args:
            cmd += ["--docker-args", args.docker_args]

    subprocess.run(cmd, check=True)


def cmd_p2p_host(args: argparse.Namespace) -> None:
    _run_p2p_subcommand(args, "host")


def cmd_p2p_receiver(args: argparse.Namespace) -> None:
    _run_p2p_subcommand(args, "receiver")


def cmd_tui(args: argparse.Namespace) -> None:
    try:
        from textual.app import App
        from textual.containers import Horizontal, Vertical
        from textual.screen import ModalScreen
        from textual.widgets import Button, DataTable, Footer, Header, Input, Label, OptionList, RichLog, Static
    except ImportError as exc:
        raise RuntimeError("Textual is not installed. Install dependencies with 'pip install -r backend/requirements.txt'.") from exc

    class FormScreen(ModalScreen):
        BINDINGS = [("escape", "cancel", "Cancel")]

        CSS = """
        FormScreen {
            align: center middle;
            background: #020711 80%;
        }
        #form-box {
            width: 72;
            max-width: 92;
            border: round #95f2bd;
            background: #0b1322;
            padding: 1 2;
        }
        .form-title { color: #95f2bd; text-style: bold; margin-bottom: 1; }
        .form-label { color: #e5e7eb; margin-top: 1; }
        #form-error { color: #ff6b6b; margin-top: 1; }
        #form-actions { margin-top: 1; height: auto; }
        Button { margin-right: 1; }
        """

        def __init__(self, title: str, fields: list[dict[str, Any]]) -> None:
            super().__init__()
            self.form_title = title
            self.fields = fields

        def compose(self):
            with Vertical(id="form-box"):
                yield Static(self.form_title, classes="form-title")
                for field in self.fields:
                    key = str(field["key"])
                    yield Label(str(field["label"]), classes="form-label")
                    yield Input(value=str(field.get("default") or ""), password=bool(field.get("password", False)), id=f"field-{key}")
                yield Static("", id="form-error")
                with Horizontal(id="form-actions"):
                    yield Button("Submit", id="form-submit", variant="success")
                    yield Button("Cancel", id="form-cancel", variant="default")

        def on_mount(self) -> None:
            if self.fields:
                first_key = str(self.fields[0]["key"])
                self.set_focus(self.query_one(f"#field-{first_key}", Input))

        def _collect_values(self):
            values: dict[str, str] = {}
            for field in self.fields:
                key = str(field["key"])
                value = self.query_one(f"#field-{key}", Input).value.strip()
                if bool(field.get("required", False)) and not value:
                    self.query_one("#form-error", Static).update(f"{field['label']} is required")
                    return None
                values[key] = value
            return values

        def on_button_pressed(self, event) -> None:
            if event.button.id == "form-cancel":
                self.dismiss(None)
                return
            values = self._collect_values()
            if values is not None:
                self.dismiss(values)

        def on_input_submitted(self, _) -> None:
            values = self._collect_values()
            if values is not None:
                self.dismiss(values)

        def action_cancel(self) -> None:
            self.dismiss(None)

    class AccessSourceScreen(ModalScreen):
        BINDINGS = [("escape", "cancel", "Cancel")]

        CSS = """
        AccessSourceScreen {
            align: center middle;
            background: #020711 80%;
        }
        #source-box {
            width: 62;
            border: round #95f2bd;
            background: #0b1322;
            padding: 1 2;
        }
        .source-title { color: #95f2bd; text-style: bold; margin-bottom: 1; }
        .source-subtitle { color: #b9cbbb; margin-bottom: 1; }
        #source-actions { height: auto; }
        Button { margin-right: 1; }
        """

        def compose(self):
            with Vertical(id="source-box"):
                yield Static("Access State Source", classes="source-title")
                yield Static("Choose where to select the job from.", classes="source-subtitle")
                with Horizontal(id="source-actions"):
                    yield Button("My Jobs", id="source-my", variant="success")
                    yield Button("Marketplace", id="source-market", variant="primary")
                    yield Button("Cancel", id="source-cancel", variant="default")

        def on_mount(self) -> None:
            self.set_focus(self.query_one("#source-my", Button))

        def on_button_pressed(self, event) -> None:
            if event.button.id == "source-my":
                self.dismiss("my")
            elif event.button.id == "source-market":
                self.dismiss("market")
            else:
                self.dismiss(None)

        def action_cancel(self) -> None:
            self.dismiss(None)

    class JobPickerScreen(ModalScreen):
        BINDINGS = [("escape", "cancel", "Cancel")]

        CSS = """
        JobPickerScreen {
            align: center middle;
            background: #020711 80%;
        }
        #picker-box {
            width: 110;
            max-width: 120;
            height: 32;
            border: round #95f2bd;
            background: #0b1322;
            padding: 1;
        }
        .picker-title { color: #95f2bd; text-style: bold; margin: 0 1 1 1; }
        #picker-table { height: 1fr; margin: 0 1; }
        #picker-input { margin: 1 1 0 1; }
        #picker-error { color: #ff6b6b; margin: 0 1; }
        #picker-actions { height: auto; margin: 1 1 0 1; }
        Button { margin-right: 1; }
        """

        def __init__(self, title: str, jobs: list[dict[str, Any]]) -> None:
            super().__init__()
            self.picker_title = title
            self.jobs = jobs

        def compose(self):
            with Vertical(id="picker-box"):
                yield Static(self.picker_title, classes="picker-title")
                yield DataTable(id="picker-table")
                yield Input(placeholder="Enter row number or manual Job ID", id="picker-input")
                yield Static("", id="picker-error")
                with Horizontal(id="picker-actions"):
                    yield Button("Select", id="picker-select", variant="success")
                    yield Button("Cancel", id="picker-cancel", variant="default")

        def on_mount(self) -> None:
            table = self.query_one("#picker-table", DataTable)
            table.cursor_type = "row"
            table.zebra_stripes = True
            table.add_columns("No", "Job ID", "Status", "Access", "Repo/File")
            if not self.jobs:
                table.add_row("-", "-", "-", "-", "No jobs")
                self.set_focus(self.query_one("#picker-cancel", Button))
                return
            for index, job in enumerate(self.jobs, start=1):
                table.add_row(str(index), str(job.get("id") or ""), str(job.get("status") or "-"), str(job.get("access_status") or "-"), str(job.get("repo_url") or job.get("filename") or "-"))
            self.set_focus(table)

        def _highlighted_job(self):
            if not self.jobs:
                return None
            table = self.query_one("#picker-table", DataTable)
            row_index = int(table.cursor_row)
            if 0 <= row_index < len(self.jobs):
                return self.jobs[row_index]
            return None

        def _selected_job(self):
            raw = self.query_one("#picker-input", Input).value.strip()
            if not raw:
                highlighted = self._highlighted_job()
                if highlighted is not None:
                    return highlighted
                self.query_one("#picker-error", Static).update("Select a row, or type manual Job ID")
                return None
            if raw.isdigit() and self.jobs:
                idx = int(raw)
                if 1 <= idx <= len(self.jobs):
                    return self.jobs[idx - 1]
                self.query_one("#picker-error", Static).update("Row number out of range")
                return None
            return {"id": raw}

        def on_data_table_row_selected(self, event) -> None:
            row_index = int(event.cursor_row)
            if 0 <= row_index < len(self.jobs):
                self.dismiss(self.jobs[row_index])

        def on_button_pressed(self, event) -> None:
            if event.button.id == "picker-cancel":
                self.dismiss(None)
                return
            selected = self._selected_job()
            if selected is not None:
                self.dismiss(selected)

        def on_input_submitted(self, _) -> None:
            selected = self._selected_job()
            if selected is not None:
                self.dismiss(selected)

        def action_cancel(self) -> None:
            self.dismiss(None)

    class RvidiaTextualApp(App):
        CSS = """
        Screen { background: #020711; color: #e5e7eb; }
        Header { background: #0f1624; color: #95f2bd; text-style: bold; }
        Footer { background: #090f16; color: #e5e7eb; }
        #layout { height: 1fr; }
        #actions-pane { width: 34; border: round #95f2bd; margin: 1 1 1 1; background: #0b1322; }
        #actions-title { color: #95f2bd; text-style: bold; margin: 1; }
        #actions { margin: 0 1 1 1; height: 1fr; background: #08101d; }
        #main-pane { border: round #7e8784; margin: 1 1 1 0; background: #0b1322; padding: 0 1 1 1; }
        #status { color: #b9cbbb; margin: 1 0; }
        #jobs-table { height: 14; margin-bottom: 1; background: #060b14; }
        #log-title { color: #95f2bd; text-style: bold; margin: 0 0 1 0; }
        #log { height: 1fr; background: #060b14; border: round #7e8784; }
        """

        BINDINGS = [("q", "quit", "Quit"), ("r", "refresh", "Refresh")]

        ACTIONS = [
            ("login", "1. Login"),
            ("signup", "2. Signup"),
            ("whoami", "3. Whoami"),
            ("create_job", "4. Create Job"),
            ("list_jobs", "5. List My Jobs"),
            ("marketplace", "6. List Marketplace"),
            ("request_access", "7. Request Access"),
            ("accept_access", "8. Accept Access"),
            ("access_state", "9. Show Access State"),
            ("p2p_host", "10. Run P2P Host"),
            ("p2p_receiver", "11. Run P2P Receiver"),
            ("switch_api", "12. Switch API Base"),
            ("logout", "13. Logout"),
        ]

        def __init__(self, api_base: str) -> None:
            super().__init__()
            self.api_base = api_base
            self.my_jobs: list[dict[str, Any]] = []
            self.market_jobs: list[dict[str, Any]] = []

        def compose(self):
            yield Header(show_clock=True)
            with Horizontal(id="layout"):
                with Vertical(id="actions-pane"):
                    yield Static("RVIDIA Actions", id="actions-title")
                    yield OptionList(*[label for _, label in self.ACTIONS], id="actions")
                with Vertical(id="main-pane"):
                    yield Static("", id="status")
                    yield DataTable(id="jobs-table")
                    yield Static("Activity", id="log-title")
                    yield RichLog(id="log", wrap=True, markup=False)
            yield Footer()

        async def on_mount(self) -> None:
            self.query_one("#jobs-table", DataTable).cursor_type = "row"
            await self.action_refresh()

        async def action_refresh(self) -> None:
            try:
                self.my_jobs, self.market_jobs = await asyncio.gather(
                    asyncio.to_thread(self._get_jobs, False),
                    asyncio.to_thread(self._get_market_jobs),
                )
                self._set_status()
                self._render_jobs_table(self.my_jobs, "My Jobs")
                self._log("Refreshed jobs and marketplace lists")
            except RuntimeError as exc:
                self._log(f"Refresh failed: {exc}", error=True)

        def _set_status(self) -> None:
            user_text = "not logged in"
            session = _load_session()
            saved_user = session.get("user")
            if isinstance(saved_user, dict):
                user_text = f"{saved_user.get('username', '-')} ({saved_user.get('email', '-')})"
            elif str(session.get("access_token") or "").strip():
                user_text = "logged in"
            self.query_one("#status", Static).update(
                f"API: {self.api_base} | User: {user_text} | My jobs: {len(self.my_jobs)} | Marketplace: {len(self.market_jobs)}"
            )

        async def _api_request_async(
            self,
            method: str,
            path: str,
            *,
            token: str | None = None,
            payload: dict[str, Any] | None = None,
        ) -> Any:
            return await asyncio.to_thread(
                _api_request,
                method,
                self.api_base,
                path,
                token,
                payload,
            )

        def _render_jobs_table(self, jobs: list[dict[str, Any]], title: str) -> None:
            table = self.query_one("#jobs-table", DataTable)
            table.clear(columns=True)
            table.add_columns(f"{title} #", "Job ID", "Status", "Access", "Repo/File", "Created")
            if not jobs:
                table.add_row("-", "-", "-", "-", "No jobs", "-")
                return
            for idx, job in enumerate(jobs, start=1):
                created = str(job.get("created_at") or "")
                try:
                    created = datetime.fromisoformat(created).strftime("%m-%d %H:%M") if created else "-"
                except ValueError:
                    pass
                table.add_row(str(idx), str(job.get("id") or ""), str(job.get("status") or "-"), str(job.get("access_status") or "-"), str(job.get("repo_url") or job.get("filename") or "-"), created)

        def _log(self, message: str, data: Any | None = None, error: bool = False) -> None:
            log = self.query_one("#log", RichLog)
            log.write(("[ERROR] " if error else "[OK] ") + message)
            if data is not None:
                log.write(json.dumps(data, indent=2, default=str))

        def _get_jobs(self, open_only: bool = False) -> list[dict[str, Any]]:
            token = _resolve_token(None)
            data = _api_request("GET", self.api_base, "/jobs/open" if open_only else "/jobs", token=token)
            return data if isinstance(data, list) else []

        def _get_market_jobs(self) -> list[dict[str, Any]]:
            token = _resolve_token(None)
            data = _api_request("GET", self.api_base, "/p2p/jobs", token=token)
            return data if isinstance(data, list) else []

        def on_option_list_option_selected(self, event) -> None:
            action_key = self.ACTIONS[event.option_index][0]
            self.run_worker(self._run_action(action_key), exclusive=True, group="actions")

        async def _push_screen_result(self, screen):
            return await self.push_screen_wait(screen)

        async def _pick_job(self, title: str, use_market: bool = False, open_only: bool = False):
            jobs = self.market_jobs if use_market else self.my_jobs
            if open_only:
                jobs = [j for j in jobs if str(j.get("status") or "") in {"queued", "in_progress", "transferring"}]
            return await self._push_screen_result(JobPickerScreen(title, jobs))

        async def _run_action(self, action_key: str) -> None:
            try:
                if action_key == "login":
                    values = await self._push_screen_result(FormScreen("Login", [{"key": "username_or_email", "label": "Username or email", "required": True}, {"key": "password", "label": "Password", "password": True, "required": True}]))
                    if not values:
                        return
                    payload = await self._api_request_async("POST", "/auth/login", payload=values)
                    token = str(payload.get("access_token") or "")
                    if not token:
                        raise RuntimeError("Login succeeded but no access_token was returned")
                    session_payload = {"api_base": self.api_base, "access_token": token}
                    try:
                        session_payload["user"] = await self._api_request_async("GET", "/auth/me", token=token)
                    except RuntimeError:
                        pass
                    _save_session(session_payload)
                    self._log("Logged in and session saved")
                    await self.action_refresh()
                elif action_key == "signup":
                    values = await self._push_screen_result(FormScreen("Signup", [{"key": "username", "label": "Username", "required": True}, {"key": "email", "label": "Email", "required": True}, {"key": "password", "label": "Password", "password": True, "required": True}, {"key": "confirm_password", "label": "Confirm password", "password": True, "required": True}]))
                    if not values:
                        return
                    self._log("Signup completed", await self._api_request_async("POST", "/auth/signup", payload=values))
                elif action_key == "whoami":
                    self._log("Current user", await self._api_request_async("GET", "/auth/me", token=_resolve_token(None)))
                elif action_key == "create_job":
                    values = await self._push_screen_result(FormScreen("Create Job", [{"key": "repo_url", "label": "Repo URL", "required": True}, {"key": "branch", "label": "Branch", "default": "main"}, {"key": "command", "label": "Command (optional)", "default": ""}]))
                    if not values:
                        return
                    self._log("Job created", await self._api_request_async("POST", "/jobs", token=_resolve_token(None), payload=values))
                    await self.action_refresh()
                elif action_key == "list_jobs":
                    self._render_jobs_table(self.my_jobs, "My Jobs")
                    self._log("Displayed your jobs", self.my_jobs)
                elif action_key == "marketplace":
                    self._render_jobs_table(self.market_jobs, "Marketplace")
                    self._log("Displayed marketplace jobs", self.market_jobs)
                elif action_key == "request_access":
                    selected = await self._pick_job("Pick marketplace job", use_market=True)
                    if not selected:
                        return
                    job_id = str(selected.get("id") or "")
                    self._log(
                        f"Requested access for job {job_id}",
                        await self._api_request_async("POST", f"/p2p/jobs/{job_id}/request-access", token=_resolve_token(None), payload={}),
                    )
                    await self.action_refresh()
                elif action_key == "accept_access":
                    selected = await self._pick_job("Pick your job to accept access")
                    if not selected:
                        return
                    job_id = str(selected.get("id") or "")
                    self._log(
                        f"Accepted access for job {job_id}",
                        await self._api_request_async("POST", f"/p2p/jobs/{job_id}/accept-access", token=_resolve_token(None), payload={}),
                    )
                    await self.action_refresh()
                elif action_key == "access_state":
                    source = await self._push_screen_result(AccessSourceScreen())
                    if not source:
                        return
                    selected = await self._pick_job("Pick job for access state", use_market=source == "market")
                    if not selected:
                        return
                    job_id = str(selected.get("id") or "")
                    self._log(
                        f"Access state for {job_id}",
                        await self._api_request_async("GET", f"/p2p/jobs/{job_id}/access", token=_resolve_token(None)),
                    )
                elif action_key == "p2p_host":
                    selected = await self._pick_job("Pick your job for host", open_only=True)
                    if not selected:
                        return
                    values = await self._push_screen_result(FormScreen("Host Options", [{"key": "workspace", "label": "Workspace", "default": "./.p2p-workspaces"}, {"key": "disable_request", "label": "Disable auto request-access (y/n)", "default": "n"}, {"key": "secret_key", "label": "Secret key (optional)", "default": ""}]))
                    if not values:
                        return
                    await asyncio.to_thread(_run_p2p_subcommand, argparse.Namespace(api_base=self.api_base, token=None, job_id=str(selected.get("id") or ""), workspace=values["workspace"] or "./.p2p-workspaces", no_request_access=values["disable_request"].strip().lower() in {"y", "yes", "1", "true"}, secret_key=values["secret_key"] or None), "host")
                    self._log("Host run completed")
                elif action_key == "p2p_receiver":
                    selected = await self._pick_job("Pick your job for receiver", open_only=True)
                    if not selected:
                        return
                    default_repo = str(selected.get("repo_url") or "")
                    values = await self._push_screen_result(FormScreen("Receiver Options", [{"key": "repo_url", "label": "Repo URL", "default": default_repo, "required": not bool(default_repo)}, {"key": "branch", "label": "Branch", "default": str(selected.get("branch") or "main")}, {"key": "docker_args", "label": "Docker args (optional)", "default": ""}, {"key": "host_node_id", "label": "Host node ID (optional)", "default": ""}, {"key": "output_dir", "label": "Output directory", "default": "./outputs"}, {"key": "workspace", "label": "Workspace", "default": "./.p2p-workspaces"}, {"key": "secret_key", "label": "Secret key (optional)", "default": ""}]))
                    if not values:
                        return
                    await asyncio.to_thread(_run_p2p_subcommand, argparse.Namespace(api_base=self.api_base, token=None, job_id=str(selected.get("id") or ""), repo_url=values["repo_url"], branch=values["branch"] or "main", docker_args=values["docker_args"], host_node_id=values["host_node_id"], output_dir=values["output_dir"] or "./outputs", workspace=values["workspace"] or "./.p2p-workspaces", secret_key=values["secret_key"] or None), "receiver")
                    self._log("Receiver run completed")
                elif action_key == "switch_api":
                    values = await self._push_screen_result(FormScreen("Switch API Base", [{"key": "api_base", "label": "API base", "default": self.api_base, "required": True}]))
                    if not values:
                        return
                    self.api_base = _resolve_api_base(values["api_base"])
                    session = _load_session()
                    if session:
                        session["api_base"] = self.api_base
                        _save_session(session)
                    self._log(f"API base switched to {self.api_base}")
                    await self.action_refresh()
                elif action_key == "logout":
                    _clear_session()
                    self._log("Logged out and cleared local session")
                    await self.action_refresh()
            except (RuntimeError, subprocess.CalledProcessError) as exc:
                self._log(str(exc), error=True)

    api_base = _resolve_api_base(args.api_base)
    app = RvidiaTextualApp(api_base=api_base)
    app.run()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RVIDIA CLI client")
    _add_connection_args(parser)

    sub = parser.add_subparsers(dest="command", required=True)

    signup = sub.add_parser("signup", help="Create account")
    _add_connection_args(signup)
    signup.add_argument("--username", required=True)
    signup.add_argument("--email", required=True)
    signup.add_argument("--password", required=True)
    signup.add_argument("--confirm-password", default=None)
    signup.set_defaults(handler=cmd_signup)

    login = sub.add_parser("login", help="Login and save local session")
    _add_connection_args(login)
    login.add_argument("--username-or-email", required=True)
    login.add_argument("--password", required=True)
    login.set_defaults(handler=cmd_login)

    logout = sub.add_parser("logout", help="Clear local session")
    _add_connection_args(logout)
    logout.set_defaults(handler=cmd_logout)

    whoami = sub.add_parser("whoami", help="Show current user")
    _add_connection_args(whoami)
    whoami.set_defaults(handler=cmd_whoami)

    create_job = sub.add_parser("create-job", help="Create a new GitHub job")
    _add_connection_args(create_job)
    create_job.add_argument("--repo-url", required=True)
    create_job.add_argument("--branch", default="main")
    create_job.add_argument("--command", default="")
    create_job.set_defaults(handler=cmd_create_job)

    list_jobs = sub.add_parser("list-jobs", help="List your jobs")
    _add_connection_args(list_jobs)
    list_jobs.add_argument("--open", action="store_true", help="List only open/in-progress jobs")
    list_jobs.set_defaults(handler=cmd_list_jobs)

    get_job = sub.add_parser("get-job", help="Get one job by ID")
    _add_connection_args(get_job)
    get_job.add_argument("--job-id", required=True)
    get_job.set_defaults(handler=cmd_get_job)

    marketplace = sub.add_parser("marketplace", help="List marketplace jobs")
    _add_connection_args(marketplace)
    marketplace.set_defaults(handler=cmd_list_marketplace)

    hosts = sub.add_parser("hosts", help="List registered hosts and GPU metadata")
    _add_connection_args(hosts)
    hosts.set_defaults(handler=cmd_list_hosts)

    request_access = sub.add_parser("request-access", help="Request access to a marketplace job")
    _add_connection_args(request_access)
    request_access.add_argument("--job-id", required=True)
    request_access.set_defaults(handler=cmd_request_access)

    accept_access = sub.add_parser("accept-access", help="Accept access request for your job")
    _add_connection_args(accept_access)
    accept_access.add_argument("--job-id", required=True)
    accept_access.set_defaults(handler=cmd_accept_access)

    access_state = sub.add_parser("access-state", help="Show access state for a job")
    _add_connection_args(access_state)
    access_state.add_argument("--job-id", required=True)
    access_state.set_defaults(handler=cmd_access_state)

    p2p_host = sub.add_parser("p2p-host", help="Run host worker for a job")
    _add_connection_args(p2p_host)
    p2p_host.add_argument("--job-id", required=True)
    p2p_host.add_argument("--workspace", default="./.p2p-workspaces")
    p2p_host.add_argument("--secret-key", default=None)
    p2p_host.add_argument("--no-request-access", action="store_true")
    p2p_host.set_defaults(handler=cmd_p2p_host)

    p2p_receiver = sub.add_parser("p2p-receiver", help="Run receiver worker for a job")
    _add_connection_args(p2p_receiver)
    p2p_receiver.add_argument("--job-id", required=True)
    p2p_receiver.add_argument("--repo-url", required=True)
    p2p_receiver.add_argument("--branch", default="main")
    p2p_receiver.add_argument("--docker-args", default="")
    p2p_receiver.add_argument("--host-node-id", default="")
    p2p_receiver.add_argument("--output-dir", default="./outputs")
    p2p_receiver.add_argument("--workspace", default="./.p2p-workspaces")
    p2p_receiver.add_argument("--secret-key", default=None)
    p2p_receiver.set_defaults(handler=cmd_p2p_receiver)

    tui = sub.add_parser("tui", help="Interactive menu mode (no flags required per action)")
    _add_connection_args(tui)
    tui.set_defaults(handler=cmd_tui)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
