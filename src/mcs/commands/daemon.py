"""`mcs daemon` — lifecycle for the MCP server process.

The daemon owns the single MemSearch engine (Milvus Lite requires one
process per DB file). CLI commands and Hermes connect to it over HTTP MCP
on localhost, so captures, searches, and the watcher all share state.

Subcommands:
  mcs daemon start             Foreground (Ctrl-C to stop).
  mcs daemon start --daemon    Double-fork to background; log to .brain/.
  mcs daemon stop              SIGTERM the background process.
  mcs daemon status            Running? pid? port?
"""
from __future__ import annotations

import os
import signal
import socket
import sys
import time
from pathlib import Path

import typer
from rich.console import Console

from mcs.config import load_settings

app = typer.Typer(name="daemon", help="MCP server lifecycle for brain/.")
console = Console()


def _pid_file() -> Path:
    return load_settings().cache_dir.resolve() / "daemon.pid"


def _log_file() -> Path:
    return load_settings().cache_dir.resolve() / "daemon.log"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_pid() -> int | None:
    p = _pid_file()
    if not p.exists():
        return None
    try:
        pid = int(p.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None
    if not _pid_alive(pid):
        p.unlink(missing_ok=True)
        return None
    return pid


def _port_listening(host: str, port: int, timeout_s: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _wait_for_port(host: str, port: int, timeout_s: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _port_listening(host, port):
            return True
        time.sleep(0.2)
    return False


def _daemonize(log_path: Path) -> None:
    """Classic double-fork; parent exits, grandchild redirects stdio to log."""
    pid = os.fork()
    if pid > 0:
        os._exit(0)
    os.setsid()
    pid = os.fork()
    if pid > 0:
        os._exit(0)
    # grandchild
    os.chdir(str(load_settings().repo_root.resolve()))
    os.umask(0)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(os.devnull, "rb", 0) as null_in:
        os.dup2(null_in.fileno(), sys.stdin.fileno())
    log_fd = open(log_path, "ab", 0)
    os.dup2(log_fd.fileno(), sys.stdout.fileno())
    os.dup2(log_fd.fileno(), sys.stderr.fileno())


def _run_server_blocking(*, watch: bool = True) -> None:
    # Late import so the CLI stays fast when just reading status.
    from mcs.server import run_server
    run_server(watch=watch)


@app.command("start")
def start(
    detach: bool = typer.Option(
        False, "--daemon", "-d",
        help="Run in background; log to .brain/daemon.log.",
    ),
    no_watch: bool = typer.Option(
        False, "--no-watch",
        help="Skip the built-in brain/ filesystem watcher.",
    ),
) -> None:
    """Start the MCP daemon (with built-in filesystem watcher)."""
    settings = load_settings()

    existing = _read_pid()
    if existing:
        console.print(f"[yellow]already running[/yellow] pid {existing}")
        raise typer.Exit(code=1)

    if _port_listening(settings.daemon_host, settings.daemon_port):
        console.print(
            f"[red]✗[/red] {settings.daemon_host}:{settings.daemon_port} "
            f"is already in use by another process."
        )
        raise typer.Exit(code=2)

    if not detach:
        watch_note = "off" if no_watch else "on"
        console.print(
            f"[cyan]starting[/cyan] daemon on "
            f"[bold]{settings.daemon_host}:{settings.daemon_port}[/bold] "
            f"[dim](watcher {watch_note} · Ctrl-C to stop)[/dim]"
        )
        _run_server_blocking(watch=not no_watch)
        return

    # Background mode
    _daemonize(_log_file())
    _pid_file().parent.mkdir(parents=True, exist_ok=True)
    _pid_file().write_text(str(os.getpid()), encoding="utf-8")
    try:
        _run_server_blocking(watch=not no_watch)
    finally:
        _pid_file().unlink(missing_ok=True)


@app.command("stop")
def stop() -> None:
    """Stop the background daemon."""
    pid = _read_pid()
    if not pid:
        console.print("[dim]not running.[/dim]")
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _pid_file().unlink(missing_ok=True)
        console.print("[dim]stale pid cleared.[/dim]")
        return
    for _ in range(50):
        if not _pid_alive(pid):
            break
        time.sleep(0.1)
    _pid_file().unlink(missing_ok=True)
    console.print(f"[green]stopped[/green] pid {pid}")


@app.command("status")
def status() -> None:
    """Report daemon state."""
    settings = load_settings()
    pid = _read_pid()
    port_alive = _port_listening(settings.daemon_host, settings.daemon_port)

    if pid and port_alive:
        console.print(
            f"[green]running[/green] "
            f"pid {pid} · {settings.daemon_host}:{settings.daemon_port}"
        )
        log = _log_file()
        if log.exists():
            console.print(f"[dim]log: {log}[/dim]")
        return

    if pid and not port_alive:
        console.print(
            f"[yellow]pid {pid} alive but port not listening[/yellow] "
            f"— daemon is starting up or stuck. `mcs daemon stop` to clear."
        )
        return

    if not pid and port_alive:
        console.print(
            f"[yellow]port {settings.daemon_port} in use by another process[/yellow]"
        )
        return

    console.print("[dim]stopped.[/dim]")


def wait_for_daemon(timeout_s: float = 10.0) -> bool:
    """Helper for tests / auto-start flows."""
    s = load_settings()
    return _wait_for_port(s.daemon_host, s.daemon_port, timeout_s=timeout_s)
