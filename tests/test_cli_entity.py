"""Tests for the `mcs entity` Typer subcommand group (--direct path)."""
from __future__ import annotations

import json
from pathlib import Path

import frontmatter
import pytest
from typer.testing import CliRunner

from mcs.adapters import entity as ent
from mcs.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ─── list ──────────────────────────────────────────────────────────────

def test_list_drafts_table(tmp_brain: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Jane Smith", extra={"role": "Recruiter"})
    ent.create_draft(kind="companies", name="Acme")

    result = runner.invoke(app, ["entity", "list", "--drafts", "--direct"])
    assert result.exit_code == 0
    assert "jane-smith" in result.stdout
    assert "acme" in result.stdout


def test_list_active_only(tmp_brain: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")
    ent.create_draft(kind="companies", name="Acme")  # still draft

    result = runner.invoke(app, ["entity", "list", "--direct"])
    assert result.exit_code == 0
    assert "jane-smith" in result.stdout
    assert "acme" not in result.stdout


def test_list_json_output(tmp_brain: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Jane Smith", extra={"role": "X"})
    ent.confirm("people/jane-smith")

    result = runner.invoke(app, ["entity", "list", "--json", "--direct"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["qualified"] == "people/jane-smith"
    assert data[0]["meta"]["role"] == "X"


def test_list_drafts_and_all_are_mutually_exclusive(tmp_brain: Path, runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["entity", "list", "--drafts", "--all", "--direct"]
    )
    assert result.exit_code != 0


# ─── show ──────────────────────────────────────────────────────────────

def test_show_prints_profile(tmp_brain: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Jane Smith", extra={"role": "Recruiter"})

    result = runner.invoke(app, ["entity", "show", "people/jane-smith", "--direct"])
    assert result.exit_code == 0
    assert "people/jane-smith" in result.stdout
    assert "Jane Smith" in result.stdout
    assert "draft" in result.stdout
    assert "Context" in result.stdout


def test_show_missing_returns_nonzero(tmp_brain: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["entity", "show", "people/nope", "--direct"])
    assert result.exit_code != 0
    assert "not found" in result.stdout.lower() or "no entity" in result.stdout.lower()


# ─── confirm ───────────────────────────────────────────────────────────

def test_confirm_promotes_with_extra_fields(tmp_brain: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Jane Smith")

    result = runner.invoke(
        app,
        [
            "entity", "confirm", "people/jane-smith",
            "--role", "Recruiter",
            "--company", "Anthropic",
            "--set", "tier=A",
            "--direct",
        ],
    )
    assert result.exit_code == 0
    assert "→ active" in result.stdout

    promoted = tmp_brain / "entities/people/jane-smith.md"
    meta = frontmatter.load(promoted).metadata
    assert meta["role"] == "Recruiter"
    assert meta["company"] == "Anthropic"
    assert meta["tier"] == "A"


def test_confirm_invalid_set_raises(tmp_brain: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    result = runner.invoke(
        app, ["entity", "confirm", "people/jane-smith", "--set", "no-equals", "--direct"]
    )
    assert result.exit_code != 0


def test_confirm_missing_draft_returns_error(tmp_brain: Path, runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["entity", "confirm", "people/nope", "--direct"]
    )
    assert result.exit_code != 0


# ─── reject ────────────────────────────────────────────────────────────

def test_reject_deletes_draft_and_logs(tmp_brain: Path, tmp_path: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Jane Smith")

    result = runner.invoke(
        app, ["entity", "reject", "people/jane-smith", "-r", "noise", "--direct"]
    )
    assert result.exit_code == 0
    assert "rejected" in result.stdout
    assert not (tmp_brain / "entities/drafts/people/jane-smith.md").exists()

    log = tmp_path / ".brain" / "rejected-entities.jsonl"
    assert log.exists()
    assert "noise" in log.read_text(encoding="utf-8")


def test_reject_active_returns_error(tmp_brain: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")

    result = runner.invoke(
        app, ["entity", "reject", "people/jane-smith", "--direct"]
    )
    assert result.exit_code != 0


# ─── merge (FR-C5) ─────────────────────────────────────────────────────

def test_merge_consolidates_via_cli(tmp_brain: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")
    ent.create_draft(kind="people", name="J Smith")
    ent.confirm("people/j-smith")

    result = runner.invoke(
        app,
        ["entity", "merge", "people/j-smith", "people/jane-smith", "-y", "--direct"],
    )
    assert result.exit_code == 0
    assert "merged → people/jane-smith" in result.stdout
    assert not (tmp_brain / "entities/people/j-smith.md").exists()


def test_merge_cancel_at_prompt(tmp_brain: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")
    ent.create_draft(kind="people", name="J Smith")
    ent.confirm("people/j-smith")

    # Default --no on the prompt aborts the merge.
    result = runner.invoke(
        app,
        ["entity", "merge", "people/j-smith", "people/jane-smith", "--direct"],
        input="n\n",
    )
    assert result.exit_code == 0
    assert "cancelled" in result.stdout
    # Both entities still exist.
    assert (tmp_brain / "entities/people/j-smith.md").exists()
    assert (tmp_brain / "entities/people/jane-smith.md").exists()


def test_merge_cross_kind_returns_error(tmp_brain: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Acme")
    ent.confirm("people/acme")
    ent.create_draft(kind="companies", name="Acme")
    ent.confirm("companies/acme")

    result = runner.invoke(
        app,
        ["entity", "merge", "people/acme", "companies/acme", "-y", "--direct"],
    )
    assert result.exit_code != 0
    assert "cross-kind" in result.stdout
