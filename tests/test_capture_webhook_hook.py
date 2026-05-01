"""Tests for the daemon-side capture → entity-extract webhook hook."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from mcs.adapters.memory import capture


# ─── fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def webhook_capture(monkeypatch: pytest.MonkeyPatch):
    """Patch fire_webhook to record calls; returns the recorder list."""
    calls: list[dict] = []

    async def _fake_fire(route, payload, *, secret, timeout=5.0, transport=None):
        calls.append({"route": route, "payload": payload, "secret": secret})
        return {"ok": True, "status_code": 200, "error": None}

    monkeypatch.setattr("mcs.adapters.hermes_client.fire_webhook", _fake_fire)
    return calls


@pytest.fixture
def webhook_enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MCS_ENTITY_EXTRACT_WEBHOOK_ENABLED", "true")
    monkeypatch.setenv("MCS_ENTITY_EXTRACT_WEBHOOK_SECRET", "topsecret")
    monkeypatch.setenv("MCS_ENTITY_EXTRACT_WEBHOOK_ROUTE", "entity-extract")


# ─── flag-off path ─────────────────────────────────────────────────────

def test_capture_skips_webhook_when_flag_off(
    tmp_brain: Path, webhook_capture: list[dict]
) -> None:
    capture(text="hello", domain="career", title="t1")
    assert webhook_capture == []


# ─── flag-on but sync caller (CLI path) ───────────────────────────────

def test_capture_skips_webhook_when_no_running_loop(
    tmp_brain: Path, webhook_enabled, webhook_capture: list[dict]
) -> None:
    # capture() is sync; called outside any async context, so loop lookup
    # raises and the helper bails. CLI --direct uses this path.
    capture(text="hello", domain="career", title="t1")
    assert webhook_capture == []


# ─── flag-on + async caller (daemon path) ─────────────────────────────

@pytest.mark.asyncio
async def test_capture_fires_webhook_when_async_and_flag_on(
    tmp_brain: Path, webhook_enabled, webhook_capture: list[dict]
) -> None:
    rec = capture(text="hello", domain="career", title="t1")
    # The fire is fire-and-forget — yield to the loop so the task runs.
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert len(webhook_capture) == 1
    call = webhook_capture[0]
    assert call["route"] == "entity-extract"
    assert call["secret"] == "topsecret"
    assert call["payload"]["capture_id"] == rec.id
    assert call["payload"]["capture_path"] == str(rec.path)
    assert call["payload"]["domain"] == "career"
    assert call["payload"]["type"] == "note"


@pytest.mark.asyncio
async def test_capture_swallows_webhook_failure(
    tmp_brain: Path, monkeypatch: pytest.MonkeyPatch, webhook_enabled
) -> None:
    """A failing webhook must not break or block the capture call."""
    async def _failing(route, payload, *, secret, timeout=5.0, transport=None):
        raise RuntimeError("boom")

    monkeypatch.setattr("mcs.adapters.hermes_client.fire_webhook", _failing)

    # capture itself should still return cleanly even though the
    # scheduled task will blow up later on the loop.
    rec = capture(text="hello", domain="career", title="t1")
    assert rec.path.exists()
    # Drain pending tasks; the exception is swallowed by asyncio.
    try:
        await asyncio.sleep(0)
    except RuntimeError:
        pass


@pytest.mark.asyncio
async def test_capture_skips_webhook_when_secret_missing(
    tmp_brain: Path, monkeypatch: pytest.MonkeyPatch, webhook_capture: list[dict]
) -> None:
    monkeypatch.setenv("MCS_ENTITY_EXTRACT_WEBHOOK_ENABLED", "true")
    monkeypatch.delenv("MCS_ENTITY_EXTRACT_WEBHOOK_SECRET", raising=False)

    capture(text="hello", domain="career", title="t1")
    await asyncio.sleep(0)

    assert webhook_capture == []
