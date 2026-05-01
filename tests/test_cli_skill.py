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
