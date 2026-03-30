import argparse
import getpass
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_API_BASE = os.getenv("RVIDIA_API_BASE", "http://localhost:8000")
DEFAULT_SESSION_PATH = Path(os.getenv("RVIDIA_CLI_SESSION", "~/.rvidia-cli/session.json")).expanduser()


def _normalize_api_base(api_base: str) -> str:
    return api_base.rstrip("/")


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

    url = f"{_normalize_api_base(api_base)}{path if path.startswith('/') else '/' + path}"
    req = request.Request(url=url, method=method, headers=_headers(token), data=data)

    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace")
            if not raw:
                return {}
            return json.loads(raw)
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(details) if details else {}
        except json.JSONDecodeError:
            parsed = {"detail": details}
        message = parsed.get("detail") if isinstance(parsed, dict) else details
        raise RuntimeError(f"API error {exc.code}: {message}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"API connection error: {exc.reason}") from exc


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


def _prompt(label: str, default: str | None = None, secret: bool = False, required: bool = False) -> str:
    while True:
        prompt_label = label
        if default is not None and default != "":
            prompt_label += f" [{default}]"
        prompt_label += ": "

        value = getpass.getpass(prompt_label) if secret else input(prompt_label)
        value = value.strip()

        if value:
            return value
        if default is not None:
            return default
        if not required:
            return ""
        print("Value is required.")


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"y", "yes", "true", "1"}


def _short(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: width - 1] + "~"


def _fmt_timestamp(value: str | None) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%m-%d %H:%M")
    except ValueError:
        return value


def _print_job_picker(title: str, jobs: list[dict[str, Any]]) -> None:
    print(f"\n{title}")
    print("=" * len(title))
    if not jobs:
        print("No jobs found.")
        return

    print(f"{'No':<4}{'Job ID':<14}{'Status':<14}{'Access':<12}{'Repo/File':<36}{'Created':<12}")
    print("-" * 92)
    for idx, job in enumerate(jobs, start=1):
        job_id = str(job.get("id") or "")
        status = str(job.get("status") or "-")
        access = str(job.get("access_status") or "-")
        repo_or_file = str(job.get("repo_url") or job.get("filename") or "-")
        created = _fmt_timestamp(job.get("created_at"))
        print(
            f"{idx:<4}{_short(job_id, 12):<14}{_short(status, 12):<14}{_short(access, 10):<12}{_short(repo_or_file, 34):<36}{_short(created, 11):<12}"
        )


def _fetch_jobs(api_base: str, open_only: bool = False) -> list[dict[str, Any]]:
    token = _resolve_token(None)
    path = "/jobs/open" if open_only else "/jobs"
    data = _api_request("GET", api_base, path, token=token)
    return data if isinstance(data, list) else []


def _fetch_marketplace_jobs(api_base: str) -> list[dict[str, Any]]:
    token = _resolve_token(None)
    data = _api_request("GET", api_base, "/p2p/jobs", token=token)
    return data if isinstance(data, list) else []


def _select_job(
    api_base: str,
    source: str,
    title: str,
    open_only: bool = False,
    allow_manual: bool = True,
) -> dict[str, Any] | None:
    while True:
        jobs = _fetch_jobs(api_base, open_only=open_only) if source == "my" else _fetch_marketplace_jobs(api_base)
        _print_job_picker(title, jobs)

        if jobs:
            prompt = "Select job number"
        else:
            prompt = "No jobs available"

        suffix = " (r=refresh"
        if allow_manual:
            suffix += ", m=manual ID"
        suffix += ", q=cancel)"

        choice = _prompt(f"{prompt}{suffix}", required=True).lower()
        if choice == "q":
            return None
        if choice == "r":
            continue
        if allow_manual and choice == "m":
            manual_id = _prompt("Enter Job ID", required=True)
            return {"id": manual_id}

        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(jobs):
                return jobs[index - 1]

        print("Invalid selection. Pick a listed number, r, m, or q.")


def _print_tui_header(api_base: str) -> None:
    print("\nRVIDIA Control Center")
    print("=====================")
    print(f"API: {api_base}")
    try:
        me = _api_request("GET", api_base, "/auth/me", token=_resolve_token(None))
        username = me.get("username") if isinstance(me, dict) else None
        email = me.get("email") if isinstance(me, dict) else None
        print(f"User: {username or '-'} ({email or '-'})")
    except RuntimeError:
        print("User: not logged in")


def cmd_tui(args: argparse.Namespace) -> None:
    api_base = _resolve_api_base(args.api_base)
    print("Launching interactive mode. Type option numbers to run actions.")

    while True:
        _print_tui_header(api_base)
        print("\nMain Menu")
        print("---------")
        print(" 1) Login")
        print(" 2) Signup")
        print(" 3) Whoami")
        print(" 4) Create Job")
        print(" 5) List My Jobs")
        print(" 6) List Marketplace Jobs")
        print(" 7) Request Access (job picker)")
        print(" 8) Accept Access (job picker)")
        print(" 9) Show Access State (job picker)")
        print("10) Run P2P Host (job picker)")
        print("11) Run P2P Receiver (job picker + auto-fill)")
        print("12) Switch API Base")
        print("13) Logout")
        print(" 0) Exit")

        choice = _prompt("Choice", required=True)

        try:
            if choice == "1":
                username_or_email = _prompt("Username or email", required=True)
                password = _prompt("Password", secret=True, required=True)
                cmd_login(
                    argparse.Namespace(
                        api_base=api_base,
                        username_or_email=username_or_email,
                        password=password,
                    )
                )
            elif choice == "2":
                username = _prompt("Username", required=True)
                email = _prompt("Email", required=True)
                password = _prompt("Password", secret=True, required=True)
                confirm_password = _prompt("Confirm password", secret=True, required=True)
                cmd_signup(
                    argparse.Namespace(
                        api_base=api_base,
                        username=username,
                        email=email,
                        password=password,
                        confirm_password=confirm_password,
                    )
                )
            elif choice == "3":
                cmd_whoami(argparse.Namespace(api_base=api_base, token=None))
            elif choice == "4":
                repo_url = _prompt("Repo URL", required=True)
                branch = _prompt("Branch", default="main")
                command = _prompt("Command (optional)", default="")
                cmd_create_job(
                    argparse.Namespace(
                        api_base=api_base,
                        token=None,
                        repo_url=repo_url,
                        branch=branch,
                        command=command,
                    )
                )
            elif choice == "5":
                open_only = _to_bool(_prompt("Open jobs only? (y/N)", default="n"))
                cmd_list_jobs(argparse.Namespace(api_base=api_base, token=None, open=open_only))
            elif choice == "6":
                cmd_list_marketplace(argparse.Namespace(api_base=api_base, token=None))
            elif choice == "7":
                selected = _select_job(
                    api_base,
                    source="market",
                    title="Marketplace Jobs (request access)",
                    allow_manual=True,
                )
                if selected is None:
                    continue
                job_id = str(selected.get("id") or "")
                cmd_request_access(argparse.Namespace(api_base=api_base, token=None, job_id=job_id))
            elif choice == "8":
                selected = _select_job(
                    api_base,
                    source="my",
                    title="Your Jobs (accept access)",
                    allow_manual=True,
                )
                if selected is None:
                    continue
                job_id = str(selected.get("id") or "")
                cmd_accept_access(argparse.Namespace(api_base=api_base, token=None, job_id=job_id))
            elif choice == "9":
                source_choice = _prompt("Check access for (1=my jobs, 2=marketplace)", default="1")
                source = "market" if source_choice == "2" else "my"
                selected = _select_job(
                    api_base,
                    source=source,
                    title="Pick Job (access state)",
                    allow_manual=True,
                )
                if selected is None:
                    continue
                job_id = str(selected.get("id") or "")
                cmd_access_state(argparse.Namespace(api_base=api_base, token=None, job_id=job_id))
            elif choice == "10":
                selected = _select_job(
                    api_base,
                    source="my",
                    title="Your Jobs (run host)",
                    open_only=True,
                    allow_manual=True,
                )
                if selected is None:
                    continue
                job_id = str(selected.get("id") or "")
                workspace = _prompt("Workspace", default="./.p2p-workspaces")
                no_request_access = _to_bool(_prompt("Disable auto request-access? (y/N)", default="n"))
                secret_key = _prompt("Secret key (optional)", default="")
                cmd_p2p_host(
                    argparse.Namespace(
                        api_base=api_base,
                        token=None,
                        job_id=job_id,
                        workspace=workspace,
                        no_request_access=no_request_access,
                        secret_key=secret_key or None,
                    )
                )
            elif choice == "11":
                selected = _select_job(
                    api_base,
                    source="my",
                    title="Your Jobs (run receiver)",
                    open_only=True,
                    allow_manual=True,
                )
                if selected is None:
                    continue
                job_id = str(selected.get("id") or "")

                default_repo = str(selected.get("repo_url") or "")
                default_branch = str(selected.get("branch") or "main")
                repo_url = _prompt("Repo URL", default=default_repo, required=not bool(default_repo))
                branch = _prompt("Branch", default=default_branch)
                docker_args = _prompt("Docker args (optional)", default="")
                host_node_id = _prompt("Host node ID (optional)", default="")
                output_dir = _prompt("Output directory", default="./outputs")
                workspace = _prompt("Workspace", default="./.p2p-workspaces")
                secret_key = _prompt("Secret key (optional)", default="")
                cmd_p2p_receiver(
                    argparse.Namespace(
                        api_base=api_base,
                        token=None,
                        job_id=job_id,
                        repo_url=repo_url,
                        branch=branch,
                        docker_args=docker_args,
                        host_node_id=host_node_id,
                        output_dir=output_dir,
                        workspace=workspace,
                        secret_key=secret_key or None,
                    )
                )
            elif choice == "12":
                new_base = _prompt("New API base", default=api_base, required=True)
                api_base = _resolve_api_base(new_base)
                print(f"API base set to: {api_base}")
            elif choice == "13":
                cmd_logout(argparse.Namespace())
            elif choice == "0":
                print("Exiting TUI.")
                return
            else:
                print("Unknown choice. Please select a number from the menu.")
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"Error: {exc}")
        except KeyboardInterrupt:
            print("\nCancelled current action.")


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
