"""Lakehouse CLI for inspecting and initializing the lakehouse stack.

Read-only helpers (status, logs, open) plus `init` to register a project. Service
lifecycle (start/stop/restart) is managed outside this CLI (e.g. systemd:
`castle-lakehouse-api.service`).
"""

import logging
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

import click
import httpx
import psutil

# Importing lakehoused.* pulls in the daemon package (via the package __init__), which
# configures logging at INFO — spewing daemon/httpx INFO lines into CLI output. Disable
# INFO-and-below globally; this gate wins even after load_config() reconfigures logging.
logging.disable(logging.INFO)

from lakehoused.auth import get_auth_password  # noqa: E402
from lakehoused.config.settings import load_config  # noqa: E402

# Default systemd unit used by `lakehouse logs` (override with --unit or
# the LAKEHOUSED_SYSTEMD_UNIT env var).
DEFAULT_SYSTEMD_UNIT = "castle-lakehouse-api.service"


def base_url() -> str:
    """Base URL of the local daemon, derived from the configured port."""
    return f"http://localhost:{load_config().port}"


def find_process_by_name(name: str) -> list[psutil.Process]:
    """Find running processes whose cmdline contains a substring."""
    processes = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info["cmdline"]
            if cmdline and any(name in arg for arg in cmdline):
                processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return processes


def get_webapp_status() -> tuple[bool, int | None]:
    """Check if the webapp dev server (vite) is running."""
    processes = find_process_by_name("vite")
    if processes:
        return True, processes[0].pid
    return False, None


class AuthError(Exception):
    """Raised when the daemon requires auth the CLI cannot satisfy."""


def get_token(url: str, password: str | None) -> str | None:
    """Return a session token, or None if the daemon has auth disabled.

    Determines whether auth is required via the public /auth/status endpoint.
    When required, exchanges the password (explicit, else the daemon's own
    LAKEHOUSED_AUTH_PASSWORD / secrets.yaml value) for a token.

    Raises:
        AuthError: auth is required but no/invalid password is available.
    """
    resp = httpx.get(f"{url}/api/v1/auth/status", timeout=5.0)
    resp.raise_for_status()
    if not resp.json().get("auth_required", False):
        return None

    pw = password or get_auth_password()
    if not pw:
        raise AuthError(
            "Daemon requires a password but none is available to the CLI. "
            "Pass --password, set LAKEHOUSED_AUTH_PASSWORD, or add auth_password "
            "to ~/.lakehoused/config/secrets.yaml."
        )

    login = httpx.post(f"{url}/api/v1/auth/login", json={"password": pw}, timeout=5.0)
    if login.status_code == 401:
        raise AuthError("Invalid password.")
    login.raise_for_status()
    return login.json()["token"]


def auth_headers(token: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


@click.group()
def cli():
    """Lakehouse - inspect and initialize the stack (lifecycle managed externally)."""
    pass


@cli.command()
def status():
    """Show daemon and webapp status (daemon checked via its HTTP API)."""
    url = base_url()

    click.echo("Lakehouse Status:")
    click.echo("-" * 40)

    # Daemon: authoritative via the API, regardless of how it was launched.
    try:
        httpx.get(f"{url}/api/v1/health", timeout=5.0).raise_for_status()
        daemon_up = True
    except Exception:
        daemon_up = False

    if not daemon_up:
        click.echo(f"Daemon:  ✗ Not reachable at {url}")
    else:
        # Try for richer details (version/uptime/root); these need auth.
        details = None
        try:
            token = get_token(url, None)
            resp = httpx.get(f"{url}/api/v1/status", headers=auth_headers(token), timeout=5.0)
            resp.raise_for_status()
            details = resp.json()
        except (AuthError, httpx.HTTPError):
            details = None

        if details:
            uptime = int(details.get("uptimeSeconds", 0))
            click.echo(f"Daemon:  ✓ Running  (v{details.get('version', '?')}, up {uptime}s)")
            click.echo(f"Root:    {details.get('rootDir', '?')}")
        else:
            click.echo("Daemon:  ✓ Running  (details need auth)")
        click.echo(f"URL:     {url}")

    # Webapp: best-effort detection of the local dev server (production is a static site).
    webapp_running, webapp_pid = get_webapp_status()
    if webapp_running:
        click.echo(f"Webapp:  ✓ Dev server running (PID {webapp_pid})")
    else:
        click.echo("Webapp:  ✗ Dev server not detected")


@cli.command()
@click.option("--url", "url", default=None, help="Webapp URL to open (default: daemon URL)")
def open(url: str | None):
    """Open the webapp in a browser."""
    target = url or base_url()
    click.echo(f"Opening {target} in browser...")
    webbrowser.open(target)


@cli.command()
@click.option(
    "-u",
    "--unit",
    default=None,
    help="systemd unit (default: $LAKEHOUSED_SYSTEMD_UNIT or castle-lakehouse-api.service)",
)
@click.option("-f", "--follow", is_flag=True, help="Follow log output (like journalctl -f)")
@click.option("-n", "--lines", default=50, help="Number of lines to show")
def logs(unit: str | None, follow: bool, lines: int):
    """View daemon logs from the systemd journal."""
    unit = unit or os.environ.get("LAKEHOUSED_SYSTEMD_UNIT", DEFAULT_SYSTEMD_UNIT)
    cmd = ["journalctl", "--user", "-u", unit, "-n", str(lines)]
    cmd.append("-f" if follow else "--no-pager")

    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        click.echo("Error: journalctl not found. `lakehouse logs` requires systemd/journald.", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        pass


@cli.command()
@click.argument("path", default=".", required=False)
@click.option("--assistant", default=None, help="Default assistant for the project")
@click.option("--name", default=None, help="Human-readable project name")
@click.option("--password", default=None, help="Daemon password (else env/secrets.yaml)")
def init(path: str, assistant: str | None, name: str | None, password: str | None):
    """Register a directory as a lakehouse project (creates its .lakehouse marker).

    The daemon creates the .lakehouse marker + metadata and registers the project;
    the directory must live under the daemon's data root.
    """
    url = base_url()
    target = Path(path).expanduser().resolve()
    if not target.is_dir():
        click.echo(f"Error: not a directory: {target}", err=True)
        sys.exit(1)

    # Authenticate (create is a gated endpoint).
    try:
        token = get_token(url, password)
    except AuthError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except httpx.HTTPError:
        click.echo(f"Error: daemon not reachable at {url}. Is it running?", err=True)
        sys.exit(1)
    headers = auth_headers(token)

    # Resolve the daemon's data root and compute the project's relative path.
    try:
        resp = httpx.get(f"{url}/api/v1/status", headers=headers, timeout=5.0)
        resp.raise_for_status()
        root = Path(resp.json()["rootDir"]).expanduser().resolve()
    except (httpx.HTTPError, KeyError) as e:
        click.echo(f"Error: could not determine daemon data root ({e}).", err=True)
        sys.exit(1)

    try:
        rel = str(target.relative_to(root))
    except ValueError:
        click.echo(
            f"Error: {target} is not inside the daemon data root ({root}). Projects must live under it.",
            err=True,
        )
        sys.exit(1)

    payload: dict = {"relative_path": rel, "create_marker": True}
    if assistant:
        payload["default_assistant"] = assistant
    if name:
        payload["metadata"] = {"name": name}

    try:
        resp = httpx.post(f"{url}/api/v1/projects/", json=payload, headers=headers, timeout=15.0)
    except httpx.HTTPError as e:
        click.echo(f"Error: failed to reach daemon: {e}", err=True)
        sys.exit(1)

    if resp.status_code == 201:
        proj = resp.json()
        click.echo(f"✓ Initialized project '{rel}' (assistant: {proj.get('default_assistant') or '—'})")
        click.echo(f"  Marker: {target / '.lakehouse'}")
    elif resp.status_code == 400 and "already a project" in resp.text:
        click.echo(f"'{rel}' is already a registered project.")
    else:
        detail = (
            resp.json().get("detail", resp.text)
            if resp.headers.get("content-type", "").startswith("application/json")
            else resp.text
        )
        click.echo(f"Error: registration failed ({resp.status_code}): {detail}", err=True)
        sys.exit(1)


def main():
    """Entry point for lakehouse CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\nInterrupted")
        sys.exit(0)


if __name__ == "__main__":
    main()
