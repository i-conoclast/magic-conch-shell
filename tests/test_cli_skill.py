"""Tests for `mcs skill` CLI + inbox source registration (Phase 11.2)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mcs.adapters import inbox
from mcs.adapters import skill_suggestion as ss
from mcs.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ─── inbox aggregator now includes skill-promotions ────────────────────

def test_inbox_list_pending_aggregates_both_sources(tmp_brain: Path) -> None:
    from mcs.adapters import entity as ent
    ent.create_draft(kind="people", name="Jane Smith")
    ss.create_draft(slug="walk-through", name="Walk Through", summary="x4 last week")

    items = inbox.list_pending()
    types = {i.type for i in items}
    assert types == {"entity-draft", "skill-promotion"}

    by_id = {i.id: i for i in items}
    assert by_id["walk-through"].payload["draft_path"].endswith("walk-through.md")


def test_inbox_act_confirms_skill_promotion(
    tmp_brain: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mcs.config import load_settings
    settings = load_settings()
    monkeypatch.setattr(settings, "repo_root", tmp_path)
    monkeypatch.setattr(
        "mcs.adapters.skill_suggestion.load_settings", lambda: settings
    )

    ss.create_draft(slug="walk-through", name="Walk Through")
    out = inbox.act("skill-promotion", "walk-through", "approve")
    assert out["status"] == "confirmed"
    assert out["target_dir"] == "planner"
    assert (tmp_path / "skills/planner/walk-through/SKILL.md").exists()


def test_inbox_act_rejects_skill_promotion(
    tmp_brain: Path, tmp_path: Path
) -> None:
    ss.create_draft(slug="noise", name="Noise")
    out = inbox.act("skill-promotion", "noise", "reject", reason="not useful")
    assert out["status"] == "rejected"
    log = tmp_path / ".brain/rejected-skill-suggestions.jsonl"
    assert "not useful" in log.read_text(encoding="utf-8")


# ─── CLI: mcs skill propose ────────────────────────────────────────────

def test_skill_propose_creates_draft(tmp_brain: Path, runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "skill", "propose", "walk-through",
            "--name", "Walk Through",
            "--summary", "x4 last week",
        ],
    )
    assert result.exit_code == 0
    assert "proposed → walk-through" in result.stdout

    suggested = ss.resolve("walk-through")
    assert suggested.summary == "x4 last week"


def test_skill_propose_default_name_from_slug(tmp_brain: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["skill", "propose", "test-skill"])
    assert result.exit_code == 0
    suggested = ss.resolve("test-skill")
    assert suggested.name == "Test Skill"


def test_skill_propose_with_body_file(
    tmp_brain: Path, tmp_path: Path, runner: CliRunner
) -> None:
    body_path = tmp_path / "body.md"
    body_path.write_text("# Custom Body\n\nlong text here\n", encoding="utf-8")

    result = runner.invoke(
        app, ["skill", "propose", "with-body", "--body", str(body_path)]
    )
    assert result.exit_code == 0
    suggested = ss.resolve("with-body")
    body = suggested.path.read_text(encoding="utf-8")
    assert "Custom Body" in body


def test_skill_propose_duplicate_returns_error(tmp_brain: Path, runner: CliRunner) -> None:
    ss.create_draft(slug="dup", name="Dup")
    result = runner.invoke(app, ["skill", "propose", "dup"])
    assert result.exit_code != 0
    assert "draft already" in result.stdout


def test_skill_list_cli_direct(tmp_brain: Path, runner: CliRunner) -> None:
    ss.create_draft(slug="one", name="One")
    ss.create_draft(slug="two", name="Two")

    result = runner.invoke(app, ["skill", "list", "--direct"])
    assert result.exit_code == 0
    assert "one" in result.stdout
    assert "two" in result.stdout


def test_skill_list_cli_json(tmp_brain: Path, runner: CliRunner) -> None:
    ss.create_draft(slug="one", name="One")
    result = runner.invoke(app, ["skill", "list", "--json", "--direct"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert any(item["slug"] == "one" for item in data)


# ─── scan (Phase 12.4) ─────────────────────────────────────────────────

def test_skill_scan_no_corpus(tmp_brain: Path, runner: CliRunner) -> None:
    """Empty brain → graceful "no corpus items in window" message."""
    result = runner.invoke(app, ["skill", "scan", "--days", "7"])
    assert result.exit_code == 0
    assert "no corpus items" in result.stdout


def test_skill_scan_no_candidates(tmp_brain: Path, runner: CliRunner) -> None:
    """Single capture → no candidates pass the gates."""
    from mcs.adapters.memory import capture
    capture(text="solo body", title="alone")

    result = runner.invoke(app, ["skill", "scan", "--days", "30"])
    assert result.exit_code == 0
    assert "no candidates met the gates" in result.stdout


def test_skill_scan_dry_run_with_candidate(
    tmp_brain: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
) -> None:
    """Patch the detector to return one candidate; --dry-run skips LLM."""
    from mcs.adapters import skill_corpus, skill_detector
    from mcs.commands import skill as skill_cmd
    from datetime import datetime
    from zoneinfo import ZoneInfo

    fake_candidate = skill_detector.SkillCandidate(
        seed_id="capture:signals/foo",
        member_ids=["capture:signals/foo", "capture:signals/bar"],
        sample_texts=["sample one", "sample two"],
        avg_score=0.85,
        earliest=datetime(2026, 4, 28, tzinfo=ZoneInfo("Asia/Seoul")),
        latest=datetime(2026, 5, 1, tzinfo=ZoneInfo("Asia/Seoul")),
        edge_count=4,
        payload={"source_types": ["capture"], "domains": ["career"]},
    )

    async def fake_find(corpus, **kwargs):
        return [fake_candidate]

    # Need a non-empty corpus so the early-return doesn't fire.
    from mcs.adapters.memory import capture
    capture(text="seed body", title="seed")

    monkeypatch.setattr(skill_cmd.skill_detector, "find_candidates", fake_find)

    result = runner.invoke(app, ["skill", "scan", "--dry-run"])
    assert result.exit_code == 0
    assert "Candidates · 1" in result.stdout
    assert "signals/foo" in result.stdout
    assert "--dry-run" in result.stdout  # the "skipping LLM" hint
    # No draft was created.
    assert ss.list_drafts() == []


def test_skill_scan_creates_draft_via_labeler(
    tmp_brain: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
) -> None:
    """End-to-end with detector + labeler both stubbed."""
    from mcs.adapters import skill_detector, skill_labeler
    from mcs.commands import skill as skill_cmd
    from datetime import datetime
    from zoneinfo import ZoneInfo

    fake_candidate = skill_detector.SkillCandidate(
        seed_id="capture:signals/foo",
        member_ids=["capture:signals/foo"],
        sample_texts=["x"],
        avg_score=0.9,
        earliest=datetime(2026, 4, 28, tzinfo=ZoneInfo("Asia/Seoul")),
        latest=datetime(2026, 5, 1, tzinfo=ZoneInfo("Asia/Seoul")),
        edge_count=1,
        payload={},
    )

    async def fake_find(corpus, **kwargs):
        return [fake_candidate]

    async def fake_label(candidates, **kwargs):
        ss.create_draft(slug="lunch-log", name="Lunch Log")
        return [
            skill_labeler.LabeledCandidate(
                candidate_seed_id="capture:signals/foo",
                status="created",
                slug="lunch-log",
                draft_path=str(ss.resolve("lunch-log").path),
            )
        ]

    from mcs.adapters.memory import capture
    capture(text="seed body", title="seed")

    monkeypatch.setattr(skill_cmd.skill_detector, "find_candidates", fake_find)
    monkeypatch.setattr(skill_cmd.skill_labeler, "label_candidates", fake_label)

    result = runner.invoke(app, ["skill", "scan"])
    assert result.exit_code == 0
    assert "lunch-log" in result.stdout
    assert "1 created" in result.stdout


# ─── Phase 13.1: memory.skill_suggestion_create_draft MCP tool ─────────

@pytest.mark.asyncio
async def test_skill_create_draft_tool_persists(tmp_brain: Path) -> None:
    from mcs.server import memory_skill_suggestion_create_draft

    out = await memory_skill_suggestion_create_draft(
        name="Lunch Log",
        slug="lunch-log",
        summary="daily lunch tracking",
        body="## 트리거\n매일 점심.\n",
        source_session_id="skill-intake-2026-05-01-x",
    )
    assert out["slug"] == "lunch-log"
    assert out["name"] == "Lunch Log"
    assert out["summary"] == "daily lunch tracking"

    sug = ss.resolve("lunch-log")
    assert sug.summary == "daily lunch tracking"


@pytest.mark.asyncio
async def test_skill_create_draft_tool_returns_error_on_duplicate(tmp_brain: Path) -> None:
    from mcs.server import memory_skill_suggestion_create_draft

    ss.create_draft(slug="dup", name="Dup")
    out = await memory_skill_suggestion_create_draft(slug="dup", name="Dup")
    assert "error" in out
    assert "draft already" in out["error"]


@pytest.mark.asyncio
async def test_skill_create_draft_tool_returns_error_on_invalid_slug(
    tmp_brain: Path,
) -> None:
    from mcs.server import memory_skill_suggestion_create_draft

    out = await memory_skill_suggestion_create_draft(name="!!!")  # can't kebab
    assert "error" in out


# ─── Phase 13.3: mcs skill new (interactive REPL) ──────────────────────

def test_skill_intake_session_name_uses_timestamp() -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from mcs.adapters.hermes_client import skill_intake_session_name

    fake_now = datetime(2026, 5, 1, 19, 0, 30, tzinfo=ZoneInfo("Asia/Seoul"))
    assert (
        skill_intake_session_name(now=fake_now)
        == "skill-intake-20260501-190030"
    )


def test_skill_new_help_lists_subcommand(runner: CliRunner) -> None:
    result = runner.invoke(app, ["skill", "--help"])
    assert result.exit_code == 0
    assert " new " in result.stdout


def test_skill_new_quits_on_empty_first_input(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner, tmp_brain: Path
) -> None:
    """Empty user input on first turn should exit cleanly without LLM call."""
    from mcs.commands import skill as skill_cmd

    called = {"n": 0}

    async def fake_run_skill(**kwargs):
        called["n"] += 1
        return {"text": "should not be called"}

    monkeypatch.setattr(skill_cmd, "run_skill", fake_run_skill)

    # Simulate empty stdin
    result = runner.invoke(app, ["skill", "new"], input="\n")
    assert result.exit_code == 0
    assert called["n"] == 0


def test_skill_new_runs_one_turn_with_opener(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner, tmp_brain: Path
) -> None:
    """Opener arg + immediate quit on second turn → exactly one Hermes call."""
    from mcs.commands import skill as skill_cmd

    seen: list[dict] = []

    async def fake_run_skill(**kwargs):
        seen.append(kwargs)
        return {"text": "ack from skill"}

    monkeypatch.setattr(skill_cmd, "run_skill", fake_run_skill)

    result = runner.invoke(
        app, ["skill", "new", "월요일 OKR 가볍게 점검"], input="quit\n"
    )
    assert result.exit_code == 0
    assert len(seen) == 1
    assert seen[0]["skill"] == "skill-intake"
    assert seen[0]["opener"] == "월요일 OKR 가볍게 점검"
    assert "ack from skill" in result.stdout
