"""Tests for the daemon-side capture → entity-extract webhook hook."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from mcs.adapters.memory import capture


# ─── fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolate_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin HOME to a tmp dir so config's ~/.hermes/.env fallback finds nothing.

    Without this, the real user's .env (which Phase 2.4 setup populates
    with MCS_ENTITY_EXTRACT_WEBHOOK_*) bleeds into "secret missing" /
    "flag off" assertions.
    """
    monkeypatch.setenv("HOME", str(tmp_path))


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


# ─── watcher path (supplement_frontmatter fires too) ───────────────────

@pytest.mark.asyncio
async def test_supplement_fires_webhook_when_rewriting(
    tmp_brain: Path, webhook_enabled, webhook_capture: list[dict]
) -> None:
    """Phase 6.1: external-drop files get the same fire as capture()."""
    from mcs.adapters.memory import supplement_frontmatter

    (tmp_brain / "signals").mkdir()
    path = tmp_brain / "signals" / "2026-05-01-drop.md"
    # No frontmatter — supplement will rewrite and fire.
    path.write_text("body only\n", encoding="utf-8")

    rewritten = supplement_frontmatter(path)
    assert rewritten is True
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert len(webhook_capture) == 1
    assert webhook_capture[0]["payload"]["capture_id"] == "2026-05-01-drop"
    assert webhook_capture[0]["payload"]["type"] == "signal"


@pytest.mark.asyncio
async def test_supplement_skips_webhook_when_no_rewrite(
    tmp_brain: Path, webhook_enabled, webhook_capture: list[dict]
) -> None:
    """File already has full frontmatter (incl. body_hash match) → no fire."""
    from mcs.adapters.memory import supplement_frontmatter, _body_hash

    (tmp_brain / "signals").mkdir()
    path = tmp_brain / "signals" / "complete.md"
    body = "body\n"
    path.write_text(
        "---\nid: complete\ntype: signal\ndomain: null\nentities: []\n"
        "created_at: '2026-05-01T00:00:00+09:00'\nsource: typed\n"
        f"body_hash: {_body_hash(body)}\n---\n\n{body}",
        encoding="utf-8",
    )
    rewritten = supplement_frontmatter(path)
    assert rewritten is False
    await asyncio.sleep(0)

    assert webhook_capture == []


# ─── Phase 7.3: domain-classify webhook fires alongside entity-extract ──

@pytest.fixture
def both_webhooks_enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MCS_ENTITY_EXTRACT_WEBHOOK_ENABLED", "true")
    monkeypatch.setenv("MCS_ENTITY_EXTRACT_WEBHOOK_SECRET", "ee-secret")
    monkeypatch.setenv("MCS_DOMAIN_CLASSIFY_WEBHOOK_ENABLED", "true")
    monkeypatch.setenv("MCS_DOMAIN_CLASSIFY_WEBHOOK_SECRET", "dc-secret")


@pytest.mark.asyncio
async def test_capture_fires_both_webhooks_when_both_enabled(
    tmp_brain: Path, both_webhooks_enabled, webhook_capture: list[dict]
) -> None:
    capture(text="hi", domain="career", title="t1")
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    routes = sorted(c["route"] for c in webhook_capture)
    assert routes == ["domain-classify", "entity-extract"]
    secrets = {c["route"]: c["secret"] for c in webhook_capture}
    assert secrets["entity-extract"] == "ee-secret"
    assert secrets["domain-classify"] == "dc-secret"


@pytest.mark.asyncio
async def test_capture_fires_only_enabled_extractors(
    tmp_brain: Path,
    monkeypatch: pytest.MonkeyPatch,
    webhook_capture: list[dict],
) -> None:
    """Only domain-classify on, entity-extract off → exactly one fire."""
    monkeypatch.setenv("MCS_DOMAIN_CLASSIFY_WEBHOOK_ENABLED", "true")
    monkeypatch.setenv("MCS_DOMAIN_CLASSIFY_WEBHOOK_SECRET", "dc-secret")
    # entity-extract flag intentionally absent

    capture(text="hi", domain="career", title="t1")
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert [c["route"] for c in webhook_capture] == ["domain-classify"]


@pytest.mark.asyncio
async def test_supplement_fires_both_webhooks(
    tmp_brain: Path, both_webhooks_enabled, webhook_capture: list[dict]
) -> None:
    """Watcher path also fans out to both extractors."""
    from mcs.adapters.memory import supplement_frontmatter

    (tmp_brain / "signals").mkdir()
    path = tmp_brain / "signals" / "drop.md"
    path.write_text("body only\n", encoding="utf-8")
    supplement_frontmatter(path)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    routes = sorted(c["route"] for c in webhook_capture)
    assert routes == ["domain-classify", "entity-extract"]
