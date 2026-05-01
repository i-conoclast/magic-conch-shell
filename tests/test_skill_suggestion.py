"""Unit tests for mcs.adapters.skill_suggestion (FR-E5 base)."""
from __future__ import annotations

import json
from pathlib import Path

import frontmatter
import pytest

from mcs.adapters import skill_suggestion as ss


# ─── create ────────────────────────────────────────────────────────────

def test_create_draft_writes_file_and_metadata(tmp_brain: Path, tmp_path: Path) -> None:
    sug = ss.create_draft(
        name="Daily Glance",
        summary="repeated 4× in past week",
        source_session_id="okr-update-2026-04-30",
    )
    assert sug.slug == "daily-glance"
    assert sug.name == "Daily Glance"
    assert sug.path == (tmp_path / ".brain/skill-suggestions/daily-glance.md").resolve()

    meta = frontmatter.load(sug.path).metadata
    assert meta["status"] == "draft"
    assert meta["summary"] == "repeated 4× in past week"
    assert meta["source_session_id"] == "okr-update-2026-04-30"
    assert "detected_at" in meta


def test_create_draft_uses_explicit_slug(tmp_brain: Path) -> None:
    sug = ss.create_draft(slug="custom", name="Whatever Name")
    assert sug.slug == "custom"


def test_create_draft_refuses_duplicate(tmp_brain: Path) -> None:
    ss.create_draft(slug="dup", name="Dup")
    with pytest.raises(ss.SuggestionAlreadyExists, match="draft already"):
        ss.create_draft(slug="dup", name="Dup")


def test_create_draft_refuses_existing_active_skill(
    tmp_brain: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Override repo_root to tmp_path so this test doesn't touch the real repo.
    from mcs.config import load_settings
    settings = load_settings()
    monkeypatch.setattr(settings, "repo_root", tmp_path)
    monkeypatch.setattr(
        "mcs.adapters.skill_suggestion.load_settings", lambda: settings
    )

    # Plant a same-slug active skill in the fake repo.
    skill_dir = tmp_path / "skills/planner/daily-glance"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("existing\n", encoding="utf-8")

    with pytest.raises(ss.SuggestionAlreadyExists, match="active skill"):
        ss.create_draft(name="Daily Glance")


def test_create_draft_default_body_has_scaffold(tmp_brain: Path) -> None:
    sug = ss.create_draft(name="Walk Through")
    body = frontmatter.load(sug.path).content
    assert "트리거" in body
    assert "당신의 역할" in body


# ─── list ──────────────────────────────────────────────────────────────

def test_list_drafts_orders_newest_first(tmp_brain: Path) -> None:
    ss.create_draft(slug="old", name="Old")
    a = ss.resolve("old")
    # Backdate the older one so the sort is deterministic.
    post = frontmatter.load(a.path)
    post["detected_at"] = "2026-04-01T00:00:00+09:00"
    a.path.write_text(
        frontmatter.dumps(frontmatter.Post(post.content, **post.metadata)) + "\n",
        encoding="utf-8",
    )
    ss.create_draft(slug="new", name="New")

    drafts = ss.list_drafts()
    assert [d.slug for d in drafts] == ["new", "old"]


def test_list_drafts_empty_when_no_dir(tmp_brain: Path) -> None:
    assert ss.list_drafts() == []


# ─── confirm / reject ──────────────────────────────────────────────────

def test_confirm_promotes_to_planner(
    tmp_brain: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mcs.config import load_settings
    settings = load_settings()
    monkeypatch.setattr(settings, "repo_root", tmp_path)
    monkeypatch.setattr(
        "mcs.adapters.skill_suggestion.load_settings", lambda: settings
    )

    ss.create_draft(slug="walk-through", name="Walk Through")
    out = ss.confirm("walk-through")
    assert out["status"] == "confirmed"
    assert out["target_dir"] == "planner"

    promoted = tmp_path / "skills/planner/walk-through/SKILL.md"
    assert promoted.exists()
    meta = frontmatter.load(promoted).metadata
    assert "status" not in meta
    assert "detected_at" not in meta
    assert meta["slug"] == "walk-through"
    assert not (tmp_path / ".brain/skill-suggestions/walk-through.md").exists()


def test_confirm_refuses_invalid_target_dir(tmp_brain: Path) -> None:
    ss.create_draft(slug="x", name="X")
    with pytest.raises(ss.SkillSuggestionError, match="invalid target_dir"):
        ss.confirm("x", target_dir="../etc")


def test_confirm_blocks_when_dest_exists(
    tmp_brain: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mcs.config import load_settings
    settings = load_settings()
    monkeypatch.setattr(settings, "repo_root", tmp_path)
    monkeypatch.setattr(
        "mcs.adapters.skill_suggestion.load_settings", lambda: settings
    )

    # Skip the create_draft active-skill check by hand-writing the draft
    # AFTER planting the destination.
    suggestions = tmp_path / ".brain/skill-suggestions"
    suggestions.mkdir(parents=True)
    (suggestions / "boom.md").write_text(
        "---\nslug: boom\nname: Boom\nstatus: draft\n"
        "detected_at: '2026-05-01T00:00:00+09:00'\n---\n\nbody\n",
        encoding="utf-8",
    )
    dest = tmp_path / "skills/planner/boom/SKILL.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("existing\n", encoding="utf-8")

    with pytest.raises(ss.SuggestionAlreadyExists, match="target already exists"):
        ss.confirm("boom")


def test_reject_deletes_draft_and_writes_log(
    tmp_brain: Path, tmp_path: Path
) -> None:
    ss.create_draft(slug="noise", name="Noise", summary="false positive")
    out = ss.reject("noise", reason="not useful")
    assert out["status"] == "rejected"
    assert out["reason"] == "not useful"
    assert not (tmp_path / ".brain/skill-suggestions/noise.md").exists()

    log = tmp_path / ".brain/rejected-skill-suggestions.jsonl"
    assert log.exists()
    [line] = log.read_text(encoding="utf-8").strip().splitlines()
    parsed = json.loads(line)
    assert parsed["slug"] == "noise"
    assert parsed["reason"] == "not useful"


def test_reject_missing_slug_raises(tmp_brain: Path) -> None:
    with pytest.raises(ss.SuggestionNotFound):
        ss.reject("nope")
