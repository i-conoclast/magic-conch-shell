"""Unit tests for mcs.adapters.inbox aggregator (FR-G3)."""
from __future__ import annotations

from pathlib import Path

import pytest

from mcs.adapters import entity as ent
from mcs.adapters import inbox


def test_list_pending_includes_entity_drafts(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith", extra={"role": "Recruiter"})
    ent.create_draft(kind="companies", name="Acme")

    items = inbox.list_pending()
    by_id = {i.id: i for i in items}
    assert "people/jane-smith" in by_id
    assert "companies/acme" in by_id
    assert by_id["people/jane-smith"].type == "entity-draft"
    assert by_id["people/jane-smith"].payload["kind"] == "people"
    assert by_id["people/jane-smith"].payload["name"] == "Jane Smith"


def test_list_pending_filters_by_type(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    items = inbox.list_pending(item_type="entity-draft")
    assert all(i.type == "entity-draft" for i in items)
    assert inbox.list_pending(item_type="skill-promotion") == []


def test_list_pending_sorts_newest_first(
    tmp_brain: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ent.create_draft(
        kind="people", name="Old Person",
        detected_at="2026-04-01T00:00:00+09:00",
    )
    ent.create_draft(
        kind="people", name="New Person",
        detected_at="2026-05-01T00:00:00+09:00",
    )
    items = inbox.list_pending()
    assert items[0].id == "people/new-person"
    assert items[1].id == "people/old-person"


def test_act_confirm_promotes_entity_draft(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    out = inbox.act(
        "entity-draft", "people/jane-smith", "approve",
        extra={"role": "Recruiter"},
    )
    assert out["status"] == "confirmed"
    assert out["id"] == "people/jane-smith"

    promoted = ent.resolve_entity("people/jane-smith")
    assert promoted.status == "active"
    assert promoted.meta["role"] == "Recruiter"


def test_act_reject_deletes_draft(tmp_brain: Path, tmp_path: Path) -> None:
    ent.create_draft(kind="people", name="Noise")
    out = inbox.act(
        "entity-draft", "people/noise", "reject", reason="not relevant"
    )
    assert out["status"] == "rejected"
    assert out["reason"] == "not relevant"

    log = tmp_path / ".brain" / "rejected-entities.jsonl"
    assert log.exists()
    assert "not relevant" in log.read_text(encoding="utf-8")


def test_act_defer_is_no_op(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    out = inbox.act("entity-draft", "people/jane-smith", "defer")
    assert out["status"] == "deferred"
    # Still pending
    assert any(
        i.id == "people/jane-smith" for i in inbox.list_pending()
    )


def test_act_unknown_type_raises(tmp_brain: Path) -> None:
    with pytest.raises(inbox.UnknownItemType):
        inbox.act("ghost-type", "x", "approve")


def test_act_unknown_action_raises(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    with pytest.raises(inbox.InboxError):
        inbox.act("entity-draft", "people/jane-smith", "yeet")
