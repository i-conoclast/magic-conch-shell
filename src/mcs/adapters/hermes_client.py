"""Hermes gateway client — HTTP API wrapper for agent-flavored CLI calls.

`mcs okr new`, `mcs brief`, and similar commands that need a dialogue
loop route through this module. It posts to Hermes's `/v1/responses`
(OpenAI-compatible), uses the `conversation: <name>` parameter for
cross-invocation continuity, and returns the flattened assistant text.

The module is deliberately short: skill logic lives in SKILL.md, and
Hermes drives the agent loop. We only supply the transport.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx


_KST = ZoneInfo("Asia/Seoul")
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8642


# ─── Errors ─────────────────────────────────────────────────────────────

class HermesError(RuntimeError):
    """Base class for Hermes gateway failures."""


class HermesUnreachable(HermesError):
    """Gateway is not listening on the configured port."""


class HermesAuthError(HermesError):
    """API key missing or rejected."""


# ─── Config resolution ─────────────────────────────────────────────────

def gateway_url() -> str:
    """Resolve the gateway base URL from env, defaulting to localhost:8642."""
    host = os.environ.get("HERMES_HOST", _DEFAULT_HOST)
    port = os.environ.get("HERMES_PORT", str(_DEFAULT_PORT))
    return f"http://{host}:{port}"


def api_key() -> str:
    """Return the Hermes API key.

    Preference order:
      1. `HERMES_API_KEY` env var (scriptable override)
      2. `API_SERVER_KEY=...` line in `~/.hermes/.env`

    Raises HermesAuthError if neither is set.
    """
    env_key = os.environ.get("HERMES_API_KEY")
    if env_key:
        return env_key

    dotenv = Path.home() / ".hermes" / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            if line.startswith("API_SERVER_KEY="):
                val = line.split("=", 1)[1].strip()
                if val:
                    return val

    raise HermesAuthError(
        "Hermes API key not found. Set HERMES_API_KEY or add "
        "API_SERVER_KEY=... to ~/.hermes/.env."
    )


# ─── Session name helpers ───────────────────────────────────────────────

def intake_session_name(now: datetime | None = None) -> str:
    """One session per intake invocation — timestamp-based so each run is fresh."""
    n = now or datetime.now(_KST)
    return f"okr-intake-{n.strftime('%Y%m%d-%H%M%S')}"


def update_session_name(objective_id: str) -> str:
    """Per-Objective name so weekly checkups share the same conversation."""
    return f"okr-update-{objective_id}"


def brief_session_name(date: str | None = None, *, now: datetime | None = None) -> str:
    """Per-day name — re-invoking the same day resumes, next day starts fresh."""
    if date:
        return f"morning-brief-{date}"
    n = now or datetime.now(_KST)
    return f"morning-brief-{n.strftime('%Y-%m-%d')}"


def sync_session_name(date: str | None = None, *, now: datetime | None = None) -> str:
    """Per-day session for capture-progress-sync.

    Same-day re-invocation resumes the batch so partially-approved
    updates aren't re-proposed; next calendar day starts fresh.
    """
    if date:
        return f"capture-progress-sync-{date}"
    n = now or datetime.now(_KST)
    return f"capture-progress-sync-{n.strftime('%Y-%m-%d')}"


def plan_session_name(date: str | None = None, *, now: datetime | None = None) -> str:
    """Per-day session for daily-plan (interactive)."""
    if date:
        return f"daily-plan-{date}"
    n = now or datetime.now(_KST)
    return f"daily-plan-{n.strftime('%Y-%m-%d')}"


# ─── Response extraction ───────────────────────────────────────────────

def _extract_text(data: dict[str, Any]) -> str:
    """Pull the assistant's visible text out of a /v1/responses payload.

    Skips any function_call / function_call_output items; returns the last
    assistant message text (usually there is only one).
    """
    text = ""
    for item in data.get("output", []) or []:
        if item.get("type") != "message":
            continue
        if item.get("role") != "assistant":
            continue
        for c in item.get("content", []) or []:
            if c.get("type") == "output_text":
                text = c.get("text", "") or text
    return text


# ─── Public API ────────────────────────────────────────────────────────

async def run_skill(
    skill: str,
    opener: str,
    *,
    conversation: str | None = None,
    timeout: float = 180.0,
) -> dict[str, Any]:
    """Invoke a Hermes skill over /v1/responses (non-streaming).

    Args:
        skill:        Slash-command name — e.g. "okr-intake".
        opener:       User message. Auto-prepends "/<skill> " if missing.
        conversation: Named session for continuity across CLI invocations.
                      Use one of the `*_session_name()` helpers.
        timeout:      Per-request timeout in seconds (default 180s — reasoning
                      models plus tool loops can take a while).

    Returns:
        {
          "id":           response id,
          "status":       "completed" | "in_progress" | ...,
          "text":         assistant visible text,
          "conversation": echoed conversation name,
          "raw":          full payload (for callers that need tool traces)
        }
    """
    prefix = f"/{skill}"
    if not opener.startswith(prefix):
        opener = f"{prefix} {opener}".strip()

    payload: dict[str, Any] = {
        "model": "hermes-agent",
        "input": opener,
        "store": True,
    }
    if conversation:
        payload["conversation"] = conversation

    url = f"{gateway_url()}/v1/responses"
    headers = {
        "Authorization": f"Bearer {api_key()}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(url, json=payload, headers=headers)
    except httpx.ConnectError as e:
        raise HermesUnreachable(
            f"Hermes gateway not reachable at {url} — "
            f"try `hermes gateway run` (or check HERMES_HOST/PORT)."
        ) from e
    except httpx.ReadTimeout as e:
        raise HermesError(
            f"Hermes response timed out after {timeout}s — "
            f"skill may be stuck or the LLM is slow."
        ) from e

    if r.status_code == 401 or r.status_code == 403:
        raise HermesAuthError(f"gateway rejected auth ({r.status_code})")
    if r.status_code != 200:
        raise HermesError(f"gateway {r.status_code}: {r.text[:200]}")

    data = r.json()
    return {
        "id": data.get("id"),
        "status": data.get("status"),
        "text": _extract_text(data),
        "conversation": conversation,
        "raw": data,
    }
