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


def test_sync_session_uses_today_by_default() -> None:
    from mcs.adapters.hermes_client import sync_session_name
    now = datetime(2026, 4, 23, 22, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    assert sync_session_name(now=now) == "capture-progress-sync-2026-04-23"


def test_sync_session_accepts_explicit_date() -> None:
    from mcs.adapters.hermes_client import sync_session_name
    assert sync_session_name(date="2026-04-22") == "capture-progress-sync-2026-04-22"


def test_plan_session_name_helpers() -> None:
    from mcs.adapters.hermes_client import plan_session_name
    now = datetime(2026, 4, 28, 6, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    assert plan_session_name(now=now) == "daily-plan-2026-04-28"
    assert plan_session_name(date="2026-05-01") == "daily-plan-2026-05-01"


def test_retro_session_name_helpers() -> None:
    from mcs.adapters.hermes_client import retro_session_name
    now = datetime(2026, 4, 28, 22, 30, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    assert retro_session_name(now=now) == "evening-retro-2026-04-28"
    assert retro_session_name(date="2026-04-22") == "evening-retro-2026-04-22"


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


# ─── Webhook helper ─────────────────────────────────────────────────────

import hashlib
import hmac
import json as _json

import httpx as _httpx

from mcs.adapters.hermes_client import (
    _sign_webhook_body,
    fire_webhook,
    webhook_url,
)


def test_webhook_url_default_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_WEBHOOK_HOST", raising=False)
    monkeypatch.delenv("HERMES_WEBHOOK_PORT", raising=False)
    monkeypatch.delenv("HERMES_HOST", raising=False)
    assert webhook_url("entity-extract") == "http://127.0.0.1:8644/webhooks/entity-extract"


def test_webhook_url_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_WEBHOOK_HOST", "10.0.0.7")
    monkeypatch.setenv("HERMES_WEBHOOK_PORT", "9999")
    assert webhook_url("foo") == "http://10.0.0.7:9999/webhooks/foo"


def test_sign_webhook_body_matches_python_reference() -> None:
    body = b'{"capture_id":"test"}'
    expected = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert _sign_webhook_body("secret", body) == expected


@pytest.mark.asyncio
async def test_fire_webhook_signs_body_and_returns_ok() -> None:
    captured: dict = {}

    def handler(request: _httpx.Request) -> _httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content
        captured["sig"] = request.headers.get("X-Webhook-Signature")
        return _httpx.Response(204)

    out = await fire_webhook(
        "entity-extract",
        {"capture_id": "2026-05-01-foo", "domain": "career"},
        secret="topsecret",
        transport=_httpx.MockTransport(handler),
    )

    assert out == {"ok": True, "status_code": 204, "error": None}
    assert captured["url"].endswith("/webhooks/entity-extract")
    assert captured["sig"] == hmac.new(
        b"topsecret", captured["body"], hashlib.sha256
    ).hexdigest()
    # body must be valid JSON and contain our payload
    assert _json.loads(captured["body"])["capture_id"] == "2026-05-01-foo"


@pytest.mark.asyncio
async def test_fire_webhook_returns_error_on_non_2xx() -> None:
    def handler(request: _httpx.Request) -> _httpx.Response:
        return _httpx.Response(401, text="bad sig")

    out = await fire_webhook(
        "entity-extract",
        {"x": 1},
        secret="topsecret",
        transport=_httpx.MockTransport(handler),
    )

    assert out["ok"] is False
    assert out["status_code"] == 401
    assert "bad sig" in (out["error"] or "")


@pytest.mark.asyncio
async def test_fire_webhook_returns_error_on_connect_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERMES_WEBHOOK_PORT", "1")
    out = await fire_webhook(
        "entity-extract", {}, secret="x", timeout=0.5
    )
    assert out["ok"] is False
    assert out["status_code"] is None
    assert "connect" in (out["error"] or "")


@pytest.mark.asyncio
async def test_fire_webhook_refuses_empty_secret() -> None:
    out = await fire_webhook("entity-extract", {}, secret="")
    assert out == {"ok": False, "status_code": None, "error": "missing secret"}
