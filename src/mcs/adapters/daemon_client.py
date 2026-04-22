"""Thin FastMCP HTTP client for talking to the mcs daemon.

Wraps connection-reachability checks and tool-call conventions so
commands can stay focused on UX.
"""
from __future__ import annotations

import socket
from typing import Any

from fastmcp import Client

from mcs.config import load_settings


class DaemonUnreachable(RuntimeError):
    """Raised when the daemon is not listening on the configured port."""


def _daemon_listening() -> bool:
    s = load_settings()
    try:
        with socket.create_connection((s.daemon_host, s.daemon_port), timeout=0.3):
            return True
    except OSError:
        return False


def require_daemon() -> str:
    """Return the daemon URL, or raise DaemonUnreachable with a helpful msg."""
    s = load_settings()
    if not _daemon_listening():
        raise DaemonUnreachable(
            f"mcs daemon not reachable at {s.daemon_host}:{s.daemon_port}. "
            f"Run `mcs daemon start --daemon` first."
        )
    return s.daemon_url


async def call_tool(name: str, args: dict[str, Any]) -> Any:
    """Open a short-lived MCP session, call a tool, return `.data`."""
    url = require_daemon()
    async with Client(url) as c:
        result = await c.call_tool(name, args)
    return result.data
