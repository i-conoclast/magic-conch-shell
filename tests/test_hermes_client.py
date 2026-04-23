"""Tests for adapters/hermes_client."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from mcs.adapters.hermes_client import (
    HermesAuthError,
    HermesError,
    HermesUnreachable,
    _extract_text,
    api_key,
    brief_session_name,
    gateway_url,
    intake_session_name,
    run_skill,
    update_session_name,
)


# ─── session name helpers ───────────────────────────────────────────────

def test_intake_session_includes_timestamp() -> None:
    now = datetime(2026, 4, 23, 9, 30, 45, tzinfo=ZoneInfo("Asia/Seoul"))
    assert intake_session_name(now) == "okr-intake-20260423-093045"


def test_intake_sessions_differ_by_second() -> None:
    t1 = datetime(2026, 4, 23, 9, 30, 45, tzinfo=ZoneInfo("Asia/Seoul"))
    t2 = datetime(2026, 4, 23, 9, 30, 46, tzinfo=ZoneInfo("Asia/Seoul"))
    assert intake_session_name(t1) != intake_session_name(t2)


def test_update_session_is_deterministic_per_objective() -> None:
    assert (
        update_session_name("2026-Q2-career-mle-role")
        == "okr-update-2026-Q2-career-mle-role"
    )


def test_brief_session_uses_today_by_default() -> None:
    now = datetime(2026, 4, 23, 7, 15, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    assert brief_session_name(now=now) == "morning-brief-2026-04-23"


def test_brief_session_accepts_explicit_date() -> None:
    assert brief_session_name(date="2026-05-01") == "morning-brief-2026-05-01"


# ─── gateway_url ────────────────────────────────────────────────────────

def test_gateway_url_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_HOST", raising=False)
    monkeypatch.delenv("HERMES_PORT", raising=False)
    assert gateway_url() == "http://127.0.0.1:8642"


def test_gateway_url_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_HOST", "10.0.0.5")
    monkeypatch.setenv("HERMES_PORT", "9000")
    assert gateway_url() == "http://10.0.0.5:9000"


# ─── api_key loading ───────────────────────────────────────────────────

def test_api_key_env_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERMES_API_KEY", "from-env")
    # File should be ignored when env is set.
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".hermes").mkdir()
    (tmp_path / ".hermes" / ".env").write_text(
        "API_SERVER_KEY=from-file\n", encoding="utf-8"
    )
    assert api_key() == "from-env"


def test_api_key_from_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HERMES_API_KEY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".hermes").mkdir()
    (tmp_path / ".hermes" / ".env").write_text(
        "SOME_OTHER=x\nAPI_SERVER_KEY=from-file\n", encoding="utf-8"
    )
    assert api_key() == "from-file"


def test_api_key_missing_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HERMES_API_KEY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    # No .hermes/.env file
    with pytest.raises(HermesAuthError):
        api_key()


# ─── _extract_text ─────────────────────────────────────────────────────

def test_extract_text_pulls_assistant_output() -> None:
    data = {
        "output": [
            {
                "type": "function_call",
                "name": "memory.search",
                "arguments": "{}",
                "call_id": "c1",
            },
            {
                "type": "function_call_output",
                "call_id": "c1",
                "output": "[]",
            },
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": "hello there"},
                ],
            },
        ]
    }
    assert _extract_text(data) == "hello there"


def test_extract_text_empty_when_no_assistant() -> None:
    data = {"output": [{"type": "function_call", "name": "x", "arguments": "{}"}]}
    assert _extract_text(data) == ""


def test_extract_text_ignores_non_assistant_roles() -> None:
    data = {
        "output": [
            {"type": "message", "role": "user", "content": [
                {"type": "output_text", "text": "user said"}
            ]},
        ]
    }
    assert _extract_text(data) == ""


# ─── run_skill error paths ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_skill_connect_error_raises_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERMES_API_KEY", "dummy")
    # Point at an unused port
    monkeypatch.setenv("HERMES_PORT", "1")
    with pytest.raises(HermesUnreachable):
        await run_skill("okr-intake", "hi")


# ─── run_skill integration (skip if gateway not up) ────────────────────

def _gateway_reachable() -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", 8642), timeout=0.3):
            return True
    except OSError:
        return False


gateway_required = pytest.mark.skipif(
    not _gateway_reachable(),
    reason="Hermes gateway not running on 127.0.0.1:8642",
)


@gateway_required
@pytest.mark.asyncio
async def test_run_skill_roundtrip_no_skill() -> None:
    """Calling the gateway without a real slash command still works."""
    out = await run_skill(
        skill="chat", opener="reply with exactly OK", timeout=60.0
    )
    assert out["status"] == "completed"
    assert isinstance(out["text"], str)
