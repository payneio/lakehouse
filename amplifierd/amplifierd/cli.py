"""Lakehouse CLI for cross-platform daemon/webapp management.

Provides simple commands to start, stop, and manage the lakehouse stack.
"""

import builtins
import contextlib
import sys
import time
import webbrowser
from pathlib import Path

import click
import psutil

from amplifier_library.storage.paths import get_log_dir


def find_webapp_dir() -> Path:
    """Find the webapp directory relative to amplifierd package location.

    Returns:
        Path to webapp directory

    Raises:
        FileNotFoundError: If webapp directory cannot be found
    """
    # Get amplifierd package directory
    amplifierd_dir = Path(__file__).parent.parent.parent

    # Webapp should be sibling to amplifierd
    webapp_dir = amplifierd_dir / "webapp"

    if not webapp_dir.exists():
        raise FileNotFoundError(f"Webapp directory not found at {webapp_dir}")

    return webapp_dir


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

    Looks for processes matching 'python -m amplifierd' pattern.
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

            # Match pattern: python -m amplifierd
            # Check if it's a python interpreter running the amplifierd module
            is_python = "python" in cmdline[0].lower()
            has_module_flag = "-m" in cmdline
            has_amplifierd = "amplifierd" in cmdline

            if is_python and has_module_flag and has_amplifierd:
                # Verify it's the actual module, not just in a path
                module_index = cmdline.index("-m") + 1
                if (
                    module_index < len(cmdline)
                    and cmdline[module_index] == "amplifierd"
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


def stop_process(proc: psutil.Process, name: str, timeout: int = 5) -> bool:
    """Stop a process gracefully.

    Args:
        proc: Process to stop
        name: Process name for logging
        timeout: Seconds to wait before force kill

    Returns:
        True if stopped successfully
    """
    try:
        click.echo(f"Stopping {name} (PID {proc.pid})...")
        proc.terminate()

        # Wait for process to terminate
        try:
            proc.wait(timeout=timeout)
            click.echo(f"{name} stopped successfully")
            return True
        except psutil.TimeoutExpired:
            click.echo(f"{name} did not stop gracefully, force killing...")
            proc.kill()
            proc.wait(timeout=2)
            click.echo(f"{name} force killed")
            return True

    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        click.echo(f"Failed to stop {name}: {e}", err=True)
        return False


@click.group()
def cli():
    """Lakehouse - Cross-platform daemon/webapp management."""
    pass


@cli.command()
@click.option("--daemon-only", is_flag=True, help="Start only the daemon")
@click.option("--webapp-only", is_flag=True, help="Start only the webapp")
def start(daemon_only: bool, webapp_only: bool):
    """Start daemon and webapp dev server."""
    try:
        if daemon_only and webapp_only:
            click.echo("Error: Cannot specify both --daemon-only and --webapp-only", err=True)
            sys.exit(1)

        # Get log directory from daemon configuration
        # This ensures we use the same location the daemon writes to
        daemon_log_dir = get_log_dir()
        daemon_log = daemon_log_dir / "daemon.log"

        # Webapp logs go in logs/webapp (sibling to logs/amplifierd)
        webapp_log_dir = daemon_log_dir.parent / "webapp"
        webapp_log_dir.mkdir(parents=True, exist_ok=True)
        webapp_log = webapp_log_dir / "webapp.log"

        # Check if already running
        daemon_running, daemon_pid = get_daemon_status()
        webapp_running, webapp_pid = get_webapp_status()

        if not webapp_only:
            if daemon_running:
                click.echo(f"Daemon already running (PID {daemon_pid})")
            else:
                # Start daemon in background
                import subprocess

                click.echo("Starting daemon...")
                daemon_cmd = [sys.executable, "-m", "amplifierd"]
                with builtins.open(str(daemon_log), "a") as log_file:
                    subprocess.Popen(
                        daemon_cmd,
                        stdout=log_file,
                        stderr=log_file,
                        start_new_session=True,
                    )

                # Wait for daemon to start
                for _ in range(10):
                    time.sleep(0.5)
                    daemon_running, daemon_pid = get_daemon_status()
                    if daemon_running:
                        click.echo(f"Daemon started (PID {daemon_pid}, logs: {daemon_log})")
                        break
                else:
                    click.echo("Warning: Daemon may not have started successfully", err=True)

        if not daemon_only:
            if webapp_running:
                click.echo(f"Webapp already running (PID {webapp_pid})")
            else:
                # Start webapp dev server in background
                webapp_dir = find_webapp_dir()
                click.echo("Starting webapp...")

                import subprocess

                webapp_cmd = ["pnpm", "run", "dev", "--host"]
                with builtins.open(str(webapp_log), "a") as log_file:
                    subprocess.Popen(
                        webapp_cmd,
                        cwd=str(webapp_dir),
                        stdout=log_file,
                        stderr=log_file,
                        start_new_session=True,
                    )

                # Wait for webapp to start
                for _ in range(10):
                    time.sleep(0.5)
                    webapp_running, webapp_pid = get_webapp_status()
                    if webapp_running:
                        click.echo(f"Webapp started (PID {webapp_pid}, logs: {webapp_log})")
                        break
                else:
                    click.echo("Warning: Webapp may not have started successfully", err=True)

        if not daemon_only and not webapp_only:
            click.echo("\nBoth services running in background")
            click.echo("  • View logs: lakehouse logs")
            click.echo("  • Check status: lakehouse status")

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        import traceback

        click.echo(f"Unexpected error: {e}", err=True)
        click.echo("Traceback:", err=True)
        click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


@cli.command()
@click.option("--daemon-only", is_flag=True, help="Stop only the daemon")
@click.option("--webapp-only", is_flag=True, help="Stop only the webapp")
def stop(daemon_only: bool, webapp_only: bool):
    """Stop daemon and webapp dev server."""
    if daemon_only and webapp_only:
        click.echo("Error: Cannot specify both --daemon-only and --webapp-only", err=True)
        sys.exit(1)

    stopped_any = False

    if not webapp_only:
        # Stop daemon
        daemon_processes = find_daemon_processes()
        if daemon_processes:
            for proc in daemon_processes:
                if stop_process(proc, "daemon"):
                    stopped_any = True
        elif not daemon_only:
            click.echo("Daemon not running")

    if not daemon_only:
        # Stop webapp
        webapp_processes = find_process_by_name("vite")
        if webapp_processes:
            for proc in webapp_processes:
                if stop_process(proc, "webapp"):
                    stopped_any = True
        elif not webapp_only:
            click.echo("Webapp not running")

    if not stopped_any and not daemon_only and not webapp_only:
        click.echo("No services running")


@cli.command()
@click.option("--daemon-only", is_flag=True, help="Restart only the daemon")
@click.option("--webapp-only", is_flag=True, help="Restart only the webapp")
@click.pass_context
def restart(ctx, daemon_only: bool, webapp_only: bool):
    """Restart daemon and webapp dev server."""
    click.echo("Restarting services...")

    # Stop
    ctx.invoke(stop, daemon_only=daemon_only, webapp_only=webapp_only)

    # Brief pause
    time.sleep(2)

    # Start
    ctx.invoke(start, daemon_only=daemon_only, webapp_only=webapp_only)


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
        click.echo("URL:     http://localhost:5173")
    else:
        click.echo("Webapp:  ✗ Not running")


@cli.command()
@click.option("--url", default="http://localhost:5173", help="Webapp URL to open")
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
