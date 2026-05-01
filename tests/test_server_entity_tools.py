"""Tests for the FastMCP entity tools exposed by mcs.server."""
from __future__ import annotations

from pathlib import Path

import pytest

from mcs.adapters import entity as ent
from mcs.adapters.memory import capture
from mcs.server import (
    memory_entity_add_backlink,
    memory_entity_confirm,
    memory_entity_create_draft,
    memory_entity_get,
    memory_entity_list,
    memory_entity_list_drafts,
    memory_entity_reject,
)


@pytest.mark.asyncio
async def test_create_draft_tool_returns_ref_dict(tmp_brain: Path) -> None:
    out = await memory_entity_create_draft(
        kind="people",
        name="Jane Smith",
        detection_confidence=0.9,
        extra={"role": "Recruiter"},
    )
    assert out["status"] == "draft"
    assert out["qualified"] == "people/jane-smith"
    assert out["meta"]["role"] == "Recruiter"
    assert out["meta"]["detection_confidence"] == 0.9


@pytest.mark.asyncio
async def test_create_draft_tool_surfaces_invalid_kind(tmp_brain: Path) -> None:
    out = await memory_entity_create_draft(kind="bad/kind", name="X")
    assert "error" in out


@pytest.mark.asyncio
async def test_list_drafts_tool_filters_by_kind(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.create_draft(kind="companies", name="Acme")

    everything = await memory_entity_list_drafts()
    assert {r["qualified"] for r in everything} == {"people/jane-smith", "companies/acme"}

    only_people = await memory_entity_list_drafts(kind="people")
    assert [r["qualified"] for r in only_people] == ["people/jane-smith"]


@pytest.mark.asyncio
async def test_list_tool_active_default_with_optional_drafts(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")
    ent.create_draft(kind="companies", name="Acme")  # still draft

    actives = await memory_entity_list()
    assert {r["qualified"] for r in actives} == {"people/jane-smith"}

    everything = await memory_entity_list(include_drafts=True)
    assert {r["qualified"] for r in everything} == {"people/jane-smith", "companies/acme"}


@pytest.mark.asyncio
async def test_confirm_tool_promotes_and_strips(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith", detection_confidence=0.9)
    out = await memory_entity_confirm("people/jane-smith", extra={"company": "Anthropic"})
    assert out["status"] == "active"
    assert out["meta"]["company"] == "Anthropic"
    assert "detection_confidence" not in out["meta"]


@pytest.mark.asyncio
async def test_confirm_tool_returns_error_for_missing_draft(tmp_brain: Path) -> None:
    out = await memory_entity_confirm("people/nope")
    assert "error" in out


@pytest.mark.asyncio
async def test_reject_tool_writes_log(tmp_brain: Path, tmp_path: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    out = await memory_entity_reject("people/jane-smith", reason="duplicate")
    assert out["slug"] == "jane-smith"
    log = tmp_path / ".brain" / "rejected-entities.jsonl"
    assert log.exists()
    assert "duplicate" in log.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_get_tool_returns_body(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    out = await memory_entity_get("people/jane-smith")
    assert out["found"] is True
    assert "Context" in out["body"]
    assert out["meta"]["status"] == "draft"


@pytest.mark.asyncio
async def test_get_tool_handles_missing(tmp_brain: Path) -> None:
    out = await memory_entity_get("people/nope")
    assert out["found"] is False
    assert out["candidates"] == []


@pytest.mark.asyncio
async def test_add_backlink_tool_idempotent(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")
    # No `entities=` so the capture hook doesn't pre-populate the back-link;
    # this test verifies the explicit tool call's own idempotency.
    rec = capture(text="x", domain="career", title="x")

    first = await memory_entity_add_backlink("people/jane-smith", str(rec.path))
    second = await memory_entity_add_backlink("people/jane-smith", str(rec.path))
    assert first == {"added": True}
    assert second == {"added": False}


@pytest.mark.asyncio
async def test_add_backlink_tool_silent_for_missing_entity(tmp_brain: Path) -> None:
    rec = capture(text="x", domain="career", title="x")
    out = await memory_entity_add_backlink("people/no-such", str(rec.path))
    assert out == {"added": False}


# ─── memory.set_domain (Phase 7.1) — colocated since domain layer's a sibling concern ─

@pytest.mark.asyncio
async def test_set_domain_tool_writes_field(tmp_brain: Path) -> None:
    from mcs.adapters.memory import capture
    from mcs.server import memory_set_domain

    rec = capture(text="hi", title="t1")
    out = await memory_set_domain(rec.id, "career")
    assert out == {"domain": "career"}


@pytest.mark.asyncio
async def test_set_domain_tool_returns_error_on_invalid(tmp_brain: Path) -> None:
    from mcs.adapters.memory import capture
    from mcs.server import memory_set_domain

    rec = capture(text="hi", title="t1")
    out = await memory_set_domain(rec.id, "bogus-domain")
    assert "error" in out


@pytest.mark.asyncio
async def test_set_domain_tool_returns_error_on_missing(tmp_brain: Path) -> None:
    from mcs.server import memory_set_domain
    out = await memory_set_domain("nonexistent-id", "career")
    assert "error" in out
