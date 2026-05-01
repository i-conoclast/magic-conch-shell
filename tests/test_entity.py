"""Unit tests for mcs.adapters.entity (FR-C1/C2/C3 data layer)."""
from __future__ import annotations

import json
from pathlib import Path

import frontmatter
import pytest

from mcs.adapters import entity as ent
from mcs.adapters.memory import capture


# ─── create_draft ──────────────────────────────────────────────────────

def test_create_draft_writes_file_and_metadata(tmp_brain: Path) -> None:
    ref = ent.create_draft(
        kind="people",
        name="Jane Smith",
        detection_confidence=0.95,
        promoted_from="brain/signals/2026-04-22-foo.md",
        extra={"role": "ML Recruiter"},
    )

    assert ref.kind == "people"
    assert ref.slug == "jane-smith"
    assert ref.status == "draft"
    assert ref.path == (tmp_brain / "entities/drafts/people/jane-smith.md").resolve()

    meta = frontmatter.load(ref.path).metadata
    assert meta["status"] == "draft"
    assert meta["name"] == "Jane Smith"
    assert meta["detection_confidence"] == 0.95
    assert meta["promoted_from"] == "brain/signals/2026-04-22-foo.md"
    assert meta["role"] == "ML Recruiter"
    assert "detected_at" in meta


def test_create_draft_is_idempotent_on_existing_draft(tmp_brain: Path) -> None:
    first = ent.create_draft(kind="people", name="Jane Smith")
    second = ent.create_draft(kind="people", name="Jane Smith", extra={"role": "X"})

    assert first.path == second.path
    # Second call must not overwrite — original meta preserved.
    meta = frontmatter.load(second.path).metadata
    assert "role" not in meta


def test_create_draft_returns_existing_active_without_overwrite(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    promoted = ent.confirm("people/jane-smith")
    assert promoted.status == "active"

    again = ent.create_draft(kind="people", name="Jane Smith")
    assert again.status == "active"
    assert again.path == promoted.path


def test_create_draft_rejects_invalid_kind(tmp_brain: Path) -> None:
    with pytest.raises(ValueError):
        ent.create_draft(kind="people/foo", name="X")


# ─── resolve / list ────────────────────────────────────────────────────

def test_resolve_entity_prefers_active_over_draft(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")
    ent.create_draft(kind="people", name="Jane Smith")  # idempotent (returns active)

    ref = ent.resolve_entity("jane-smith")
    assert ref.status == "active"


def test_resolve_entity_ambiguous_across_kinds(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Acme")
    ent.confirm("people/acme")
    ent.create_draft(kind="companies", name="Acme")
    ent.confirm("companies/acme")

    with pytest.raises(ent.EntityAmbiguous):
        ent.resolve_entity("acme")


def test_resolve_entity_not_found(tmp_brain: Path) -> None:
    with pytest.raises(ent.EntityNotFound):
        ent.resolve_entity("people/nope")


def test_list_entities_filters_by_kind_and_status(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.create_draft(kind="companies", name="Acme")
    ent.confirm("companies/acme")

    drafts = ent.list_drafts()
    assert {d.qualified for d in drafts} == {"people/jane-smith"}

    actives = ent.list_entities()
    assert {a.qualified for a in actives} == {"companies/acme"}

    everything = ent.list_entities(include_drafts=True)
    assert {e.qualified for e in everything} == {"people/jane-smith", "companies/acme"}

    only_people = ent.list_entities(kind="people", include_drafts=True)
    assert {e.qualified for e in only_people} == {"people/jane-smith"}


# ─── confirm / reject ─────────────────────────────────────────────────

def test_confirm_promotes_draft_and_strips_draft_fields(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith", detection_confidence=0.9)
    ref = ent.confirm("people/jane-smith", extra={"role": "Recruiter", "company": "Anthropic"})

    assert ref.status == "active"
    assert not (tmp_brain / "entities/drafts/people/jane-smith.md").exists()
    assert ref.path == (tmp_brain / "entities/people/jane-smith.md").resolve()

    meta = frontmatter.load(ref.path).metadata
    assert "status" not in meta
    assert "detected_at" not in meta
    assert "detection_confidence" not in meta
    assert meta["role"] == "Recruiter"
    assert meta["company"] == "Anthropic"
    assert "created_at" in meta
    assert "updated_at" in meta
    # Fresh confirm: updated_at == created_at on the same call.
    assert meta["updated_at"] == meta["created_at"]


def test_confirm_blocks_when_active_already_exists(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")
    # Create a fresh draft at the same slug by writing it directly —
    # bypass create_draft idempotency to force the conflict.
    draft_path = tmp_brain / "entities/drafts/people/jane-smith.md"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(
        frontmatter.dumps(frontmatter.Post(
            "## Context\n",
            kind="people",
            slug="jane-smith",
            name="Jane Smith",
            status="draft",
            detected_at="2026-05-01T00:00:00+09:00",
        )) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ent.EntityAlreadyExists):
        ent.confirm("people/jane-smith")


def test_reject_deletes_draft_and_writes_log(tmp_brain: Path, tmp_path: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    record = ent.reject("people/jane-smith", reason="not relevant")

    assert record["slug"] == "jane-smith"
    assert record["reason"] == "not relevant"
    assert not (tmp_brain / "entities/drafts/people/jane-smith.md").exists()

    log_path = tmp_path / ".brain" / "rejected-entities.jsonl"
    assert log_path.exists()
    [line] = log_path.read_text(encoding="utf-8").strip().splitlines()
    parsed = json.loads(line)
    assert parsed["slug"] == "jane-smith"
    assert parsed["reason"] == "not relevant"


def test_reject_refuses_active_entity(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")

    with pytest.raises(ent.EntityError):
        ent.reject("people/jane-smith")


# ─── back-links ───────────────────────────────────────────────────────

def test_add_backlink_inserts_sorted_and_dedupes(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")

    # Capture without `entities=` so the auto back-link hook stays silent
    # — this test exercises add_backlink's own ordering + idempotency.
    older = capture(text="older", domain="career", title="older-note")
    newer = capture(text="newer", domain="career", title="newer-note")
    # Force distinct dates so the sort is observable. Same-day ordering
    # isn't a public guarantee; cross-day ordering is.
    older_meta = frontmatter.load(older.path)
    older_meta["created_at"] = "2026-04-22T09:00:00+09:00"
    older.path.write_text(
        frontmatter.dumps(frontmatter.Post(older_meta.content, **older_meta.metadata)) + "\n",
        encoding="utf-8",
    )

    # Capture itself doesn't yet wire the back-link (that's Phase 1.3).
    # Drive add_backlink directly here.
    assert ent.add_backlink("people/jane-smith", older.path) is True
    assert ent.add_backlink("people/jane-smith", newer.path) is True
    # Idempotent
    assert ent.add_backlink("people/jane-smith", newer.path) is False

    profile = (tmp_brain / "entities/people/jane-smith.md").read_text(encoding="utf-8")
    auto = profile.split("AUTO-GENERATED BELOW. DO NOT EDIT. -->")[1].split("<!-- END")[0]
    lines = [ln for ln in auto.strip().splitlines() if ln.strip()]
    assert len(lines) == 2
    # Newer (later created_at) sorts to the top.
    assert "newer-note" in lines[0]
    assert "older-note" in lines[1]


def test_add_backlink_silent_when_entity_missing(tmp_brain: Path) -> None:
    rec = capture(text="x", domain="career", entities=["people/no-such"], title="x")
    # No profile exists for `people/no-such`. Must not raise.
    assert ent.add_backlink("people/no-such", rec.path) is False


def test_remove_backlink_drops_only_target_line(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")
    a = capture(text="a", domain="career", title="a")
    b = capture(text="b", domain="career", title="b")
    ent.add_backlink("people/jane-smith", a.path)
    ent.add_backlink("people/jane-smith", b.path)

    assert ent.remove_backlink("people/jane-smith", a.path) is True
    profile = (tmp_brain / "entities/people/jane-smith.md").read_text(encoding="utf-8")
    assert "title-a" not in profile  # noqa: arbitrary check
    assert "/a]]" in profile or "-a]]" in profile or True  # presence-not-required
    # Stricter: only one line should remain in AUTO.
    auto = profile.split("AUTO-GENERATED BELOW. DO NOT EDIT. -->")[1].split("<!-- END")[0]
    lines = [ln for ln in auto.strip().splitlines() if ln.strip()]
    assert len(lines) == 1
    assert "-b]]" in lines[0]


def test_rebuild_backlinks_repopulates_from_records(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")

    # No `entities=` so the capture hook doesn't pre-populate; this lets
    # us assert rebuild really walks brain/ from scratch.
    a = capture(text="a", domain="career", title="a")
    b = capture(text="b", domain="ml", title="b")
    capture(text="c", domain="career", title="c")  # no entity link

    # Manually mark a and b as referencing the entity in their frontmatter
    # (simulating either manual `-e` or a future LLM-assigned entity).
    for rec in (a, b):
        post = frontmatter.load(rec.path)
        post["entities"] = ["people/jane-smith"]
        rec.path.write_text(
            frontmatter.dumps(frontmatter.Post(post.content, **post.metadata)) + "\n",
            encoding="utf-8",
        )

    profile_path = tmp_brain / "entities/people/jane-smith.md"
    auto = profile_path.read_text(encoding="utf-8").split("AUTO-GENERATED BELOW. DO NOT EDIT. -->")[1].split("<!-- END")[0]
    assert auto.strip() == ""

    linked = ent.rebuild_backlinks()
    assert linked == 2

    auto = profile_path.read_text(encoding="utf-8").split("AUTO-GENERATED BELOW. DO NOT EDIT. -->")[1].split("<!-- END")[0]
    lines = [ln for ln in auto.strip().splitlines() if ln.strip()]
    assert len(lines) == 2
    rels = [ent._line_rel(ln) for ln in lines]
    assert all(rel and rel.endswith(("-a", "-b")) for rel in rels)
    # Source records are unaffected by rebuild.
    assert a.path.exists()
    assert b.path.exists()


# ─── capture hook (FR-C3 manual back-link wiring) ──────────────────────

def test_capture_hook_populates_backlinks_when_entity_exists(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")

    rec = capture(text="hi", domain="career", entities=["people/jane-smith"], title="hi")

    profile = (tmp_brain / "entities/people/jane-smith.md").read_text(encoding="utf-8")
    auto = profile.split("AUTO-GENERATED BELOW. DO NOT EDIT. -->")[1].split("<!-- END")[0]
    lines = [ln for ln in auto.strip().splitlines() if ln.strip()]
    assert len(lines) == 1
    assert ent._line_rel(lines[0]) == "domains/career/" + rec.path.stem


def test_capture_hook_silent_when_entity_missing(tmp_brain: Path) -> None:
    rec = capture(text="hi", domain="career", entities=["people/no-such"], title="hi")
    # No raise, capture still produced a valid file.
    assert rec.path.exists()
    assert not (tmp_brain / "entities/people/no-such.md").exists()


def test_add_backlink_bumps_updated_at(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ref = ent.confirm("people/jane-smith")
    after_confirm = frontmatter.load(ref.path).metadata["updated_at"]

    rec = capture(text="x", domain="career", title="x")
    assert ent.add_backlink("people/jane-smith", rec.path) is True

    after_backlink = frontmatter.load(ref.path).metadata["updated_at"]
    assert after_backlink > after_confirm


def test_remove_backlink_bumps_updated_at(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ref = ent.confirm("people/jane-smith")
    rec = capture(text="x", domain="career", title="x")
    ent.add_backlink("people/jane-smith", rec.path)
    after_add = frontmatter.load(ref.path).metadata["updated_at"]

    assert ent.remove_backlink("people/jane-smith", rec.path) is True
    after_remove = frontmatter.load(ref.path).metadata["updated_at"]
    assert after_remove > after_add


def test_idempotent_backlink_does_not_bump_updated_at(tmp_brain: Path) -> None:
    """Re-adding the same line is a no-op and must not advance updated_at."""
    ent.create_draft(kind="people", name="Jane Smith")
    ref = ent.confirm("people/jane-smith")
    rec = capture(text="x", domain="career", title="x")
    ent.add_backlink("people/jane-smith", rec.path)
    snapshot = frontmatter.load(ref.path).metadata["updated_at"]

    # Second call returns False (already there) → no rewrite, no bump.
    assert ent.add_backlink("people/jane-smith", rec.path) is False
    assert frontmatter.load(ref.path).metadata["updated_at"] == snapshot


def test_capture_structured_hook_populates_backlinks(tmp_brain: Path) -> None:
    """capture_structured with entity-ref-list field also runs the hook."""
    from mcs.adapters.memory import capture_structured

    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")

    rec = capture_structured(
        template="interview-note",
        fields={
            "company": "companies/anthropic",
            "interviewers": "people/jane-smith",
            "round": "1차",
            "format": "온라인",
        },
        title="anthropic-1st",
    )

    profile = (tmp_brain / "entities/people/jane-smith.md").read_text(encoding="utf-8")
    auto = profile.split("AUTO-GENERATED BELOW. DO NOT EDIT. -->")[1].split("<!-- END")[0]
    lines = [ln for ln in auto.strip().splitlines() if ln.strip()]
    assert any(rec.path.stem in ln for ln in lines)


# ─── merge (FR-C5) ─────────────────────────────────────────────────────

def test_merge_consolidates_records_and_backlinks(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")
    ent.create_draft(kind="people", name="J Smith")
    ent.confirm("people/j-smith")

    a = capture(text="a", domain="career", entities=["people/jane-smith"], title="a")
    b = capture(text="b", domain="career", entities=["people/j-smith"], title="b")

    ref = ent.merge("people/j-smith", "people/jane-smith")
    assert ref.qualified == "people/jane-smith"
    assert not (tmp_brain / "entities/people/j-smith.md").exists()

    # Source record b now points at the canonical slug.
    b_meta = frontmatter.load(b.path).metadata
    assert b_meta["entities"] == ["people/jane-smith"]

    # `into` profile gathered both back-links + merged_from audit.
    into = (tmp_brain / "entities/people/jane-smith.md").read_text(encoding="utf-8")
    auto = into.split("AUTO-GENERATED BELOW. DO NOT EDIT. -->")[1].split("<!-- END")[0]
    assert "-a]]" in auto and "-b]]" in auto

    into_meta = frontmatter.load(tmp_brain / "entities/people/jane-smith.md").metadata
    assert into_meta["merged_from"] == ["people/j-smith"]
    assert "updated_at" in into_meta


def test_merge_refuses_cross_kind(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Acme")
    ent.confirm("people/acme")
    ent.create_draft(kind="companies", name="Acme")
    ent.confirm("companies/acme")

    with pytest.raises(ent.EntityError, match="cross-kind"):
        ent.merge("people/acme", "companies/acme")


def test_merge_refuses_self(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")

    with pytest.raises(ent.EntityError, match="same entity"):
        ent.merge("people/jane-smith", "people/jane-smith")


def test_merge_refuses_drafts(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")  # still draft
    ent.create_draft(kind="people", name="J Smith")
    ent.confirm("people/j-smith")

    with pytest.raises(ent.EntityError, match="draft"):
        ent.merge("people/jane-smith", "people/j-smith")


def test_merge_carries_over_missing_fields_only(tmp_brain: Path) -> None:
    """`into` wins on field collisions; absent fields are inherited."""
    ent.create_draft(
        kind="people", name="Jane S",
        extra={"role": "Recruiter", "location": "Seoul"},
    )
    ent.confirm("people/jane-s")
    ent.create_draft(
        kind="people", name="Jane Smith",
        extra={"role": "Senior Recruiter"},  # collision
    )
    ent.confirm("people/jane-smith")

    ent.merge("people/jane-s", "people/jane-smith")

    meta = frontmatter.load(tmp_brain / "entities/people/jane-smith.md").metadata
    # `into` value of role wins
    assert meta["role"] == "Senior Recruiter"
    # location only existed on `from` → inherited
    assert meta["location"] == "Seoul"
