"""Lakehouse CLI for inspecting the lakehouse stack.

Provides status, log, and browser helpers. Service lifecycle (start/stop/restart)
is managed outside this CLI (e.g. systemd: `castle-lakehouse-api.service`).
"""

import builtins
import contextlib
import sys
import webbrowser
from pathlib import Path

import click
import psutil

from lakehoused.storage.paths import get_log_dir


def find_process_by_name(name: str) -> list[psutil.Process]:
    """Find running processes matching a name pattern.

    Args:
        name: Process name or cmdline substring to match

    Returns:
        List of matching Process objects
    """
    processes = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info["cmdline"]
            if cmdline and any(name in arg for arg in cmdline):
                processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return processes


def find_daemon_processes() -> list[psutil.Process]:
    """Find all running daemon processes.

    Looks for processes matching 'python -m lakehoused' pattern.
    Excludes the lakehouse CLI itself and verifies processes are alive.

    Returns:
        List of daemon Process objects
    """
    current_pid = psutil.Process().pid
    daemon_processes = []

    for proc in psutil.process_iter(["pid", "cmdline", "status"]):
        try:
            # Skip current process (lakehouse CLI itself)
            if proc.info["pid"] == current_pid:
                continue

            # Skip zombie/dead processes
            if proc.info["status"] in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                continue

            cmdline = proc.info["cmdline"]
            if not cmdline or len(cmdline) < 2:
                continue

            # Match pattern: python -m lakehoused
            # Check if it's a python interpreter running the lakehoused module
            is_python = "python" in cmdline[0].lower()
            has_module_flag = "-m" in cmdline
            has_lakehoused = "lakehoused" in cmdline

            if is_python and has_module_flag and has_lakehoused:
                # Verify it's the actual module, not just in a path
                module_index = cmdline.index("-m") + 1
                if (
                    module_index < len(cmdline)
                    and cmdline[module_index] == "lakehoused"
                    and proc.is_running()
                    and proc.status() != psutil.STATUS_ZOMBIE
                ):
                    daemon_processes.append(proc)

        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, IndexError):
            continue

    return daemon_processes


def get_daemon_status() -> tuple[bool, int | None]:
    """Check if daemon is running.

    Returns:
        Tuple of (is_running, pid)
    """
    processes = find_daemon_processes()
    if processes:
        return True, processes[0].pid
    return False, None


def get_webapp_status() -> tuple[bool, int | None]:
    """Check if webapp dev server is running.

    Returns:
        Tuple of (is_running, pid)
    """
    processes = find_process_by_name("vite")
    if processes:
        return True, processes[0].pid
    return False, None


@click.group()
def cli():
    """Lakehouse - inspect the daemon/webapp stack (lifecycle managed externally)."""
    pass


@cli.command()
def status():
    """Show running status of services."""
    daemon_running, daemon_pid = get_daemon_status()
    webapp_running, webapp_pid = get_webapp_status()

    click.echo("Lakehouse Status:")
    click.echo("-" * 40)

    if daemon_running:
        click.echo(f"Daemon:  ✓ Running (PID {daemon_pid})")
    else:
        click.echo("Daemon:  ✗ Not running")

    if webapp_running:
        click.echo(f"Webapp:  ✓ Running (PID {webapp_pid})")
        click.echo("URL:     http://localhost:7777")
    else:
        click.echo("Webapp:  ✗ Not running")


@cli.command()
@click.option("--url", default="http://localhost:7777", help="Webapp URL to open")
def open(url: str):
    """Open webapp in browser."""
    webapp_running, _ = get_webapp_status()

    if not webapp_running:
        click.echo("Warning: Webapp doesn't appear to be running", err=True)
        if not click.confirm("Open browser anyway?"):
            return

    click.echo(f"Opening {url} in browser...")
    webbrowser.open(url)


def show_log_file(log_file: Path, lines: int, follow: bool = False):
    """Display log file contents.

    Args:
        log_file: Path to log file
        lines: Number of lines to show
        follow: Whether to follow log output (like tail -f)
    """
    if not log_file.exists():
        click.echo(f"No logs found at {log_file}")
        return

    if follow:
        # Tail -f equivalent
        import subprocess

        with contextlib.suppress(KeyboardInterrupt):
            subprocess.run(["tail", "-f", str(log_file)])
    else:
        # Show last N lines
        with builtins.open(log_file) as f:
            all_lines = f.readlines()
            for line in all_lines[-lines:]:
                click.echo(line.rstrip())


@cli.command()
@click.option("--daemon", is_flag=True, help="Show daemon logs only")
@click.option("--webapp", is_flag=True, help="Show webapp logs only")
@click.option("-f", "--follow", is_flag=True, help="Follow log output (like tail -f)")
@click.option("-n", "--lines", default=50, help="Number of lines to show")
def logs(daemon: bool, webapp: bool, follow: bool, lines: int):
    """View daemon and webapp logs."""
    # Get log directories from daemon configuration
    daemon_log_dir = get_log_dir()
    webapp_log_dir = daemon_log_dir.parent / "webapp"

    if daemon and webapp:
        click.echo("Error: Cannot specify both --daemon and --webapp", err=True)
        sys.exit(1)

    if daemon:
        log_file = daemon_log_dir / "daemon.log"
        show_log_file(log_file, lines, follow)
    elif webapp:
        log_file = webapp_log_dir / "webapp.log"
        show_log_file(log_file, lines, follow)
    else:
        # Show both - daemon first, then webapp
        click.echo("=== Daemon Logs ===")
        show_log_file(daemon_log_dir / "daemon.log", lines)
        click.echo("\n=== Webapp Logs ===")
        show_log_file(webapp_log_dir / "webapp.log", lines)


def main():
    """Entry point for lakehouse CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\nInterrupted")
        sys.exit(0)


if __name__ == "__main__":
    main()
