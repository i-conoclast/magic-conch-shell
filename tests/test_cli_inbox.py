"""Tests for `mcs inbox` CLI + memory.inbox_* MCP tools (Phase 10.2)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mcs.adapters import entity as ent
from mcs.cli import app
from mcs.server import memory_inbox_act, memory_inbox_list


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ─── MCP tool wrappers ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_inbox_list_tool_includes_entity_drafts(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    out = await memory_inbox_list()
    assert any(r["id"] == "people/jane-smith" for r in out)
    assert all("type" in r and "summary" in r for r in out)


@pytest.mark.asyncio
async def test_inbox_act_tool_confirm(tmp_brain: Path) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    out = await memory_inbox_act(
        "entity-draft", "people/jane-smith", "approve",
        extra={"role": "Recruiter"},
    )
    assert out["status"] == "confirmed"


@pytest.mark.asyncio
async def test_inbox_act_tool_unknown_type_returns_error(tmp_brain: Path) -> None:
    out = await memory_inbox_act("ghost", "x", "approve")
    assert "error" in out


# ─── CLI ───────────────────────────────────────────────────────────────

def test_inbox_list_cli_shows_entity_drafts(tmp_brain: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Jane Smith", extra={"role": "Recruiter"})

    result = runner.invoke(app, ["inbox", "list", "--direct"])
    assert result.exit_code == 0
    assert "entity-draft" in result.stdout
    assert "people/jane-smith" in result.stdout
    assert "Jane Smith" in result.stdout


def test_inbox_list_cli_empty(tmp_brain: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["inbox", "list", "--direct"])
    assert result.exit_code == 0
    assert "empty" in result.stdout.lower()


def test_inbox_list_cli_filter_type(tmp_brain: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    result = runner.invoke(
        app, ["inbox", "list", "--type", "skill-promotion", "--direct"]
    )
    assert result.exit_code == 0
    assert "people/jane-smith" not in result.stdout


def test_inbox_list_cli_json(tmp_brain: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    result = runner.invoke(app, ["inbox", "list", "--json", "--direct"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert any(r["id"] == "people/jane-smith" for r in data)


def test_inbox_approve_cli_with_typed_id(tmp_brain: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    result = runner.invoke(
        app,
        [
            "inbox", "approve",
            "entity-draft/people/jane-smith",
            "--set", "role=Recruiter",
            "--direct",
        ],
    )
    assert result.exit_code == 0
    promoted = ent.resolve_entity("people/jane-smith")
    assert promoted.status == "active"
    assert promoted.meta["role"] == "Recruiter"


def test_inbox_reject_cli_logs_reason(
    tmp_brain: Path, tmp_path: Path, runner: CliRunner
) -> None:
    ent.create_draft(kind="people", name="Noise")
    result = runner.invoke(
        app,
        [
            "inbox", "reject",
            "entity-draft/people/noise",
            "-r", "duplicate",
            "--direct",
        ],
    )
    assert result.exit_code == 0
    log = tmp_path / ".brain" / "rejected-entities.jsonl"
    assert "duplicate" in log.read_text(encoding="utf-8")


def test_inbox_approve_requires_typed_id_or_flag(
    tmp_brain: Path, runner: CliRunner
) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    result = runner.invoke(
        app, ["inbox", "approve", "no-prefix", "--direct"]
    )
    assert result.exit_code != 0


def test_inbox_approve_with_type_flag(tmp_brain: Path, runner: CliRunner) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    result = runner.invoke(
        app,
        [
            "inbox", "approve",
            "people/jane-smith",
            "--type", "entity-draft",
            "--direct",
        ],
    )
    assert result.exit_code == 0
