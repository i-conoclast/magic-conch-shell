"""Tests for `mcs reindex` CLI + memory.reindex MCP tool (FR-I2 / F-81)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mcs.adapters import entity as ent
from mcs.cli import app
from mcs.server import memory_reindex


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ─── MCP tool ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reindex_tool_backlinks_only(
    tmp_brain: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Skipping vectors avoids hitting MemSearch/embeddings in the test."""
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")

    out = await memory_reindex(vectors=False, backlinks=True)
    assert out["vectors"] is None
    # rebuild_backlinks returns int (count of pairs); 0 is fine here.
    assert isinstance(out["backlinks"], int)


@pytest.mark.asyncio
async def test_reindex_tool_rejects_empty_run(tmp_brain: Path) -> None:
    out = await memory_reindex(vectors=False, backlinks=False)
    assert "error" in out


@pytest.mark.asyncio
async def test_reindex_tool_calls_rebuild_all_when_vectors_true(
    tmp_brain: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[bool] = []

    async def fake_rebuild_all() -> int:
        calls.append(True)
        return 7

    monkeypatch.setattr("mcs.server.core_rebuild_all", fake_rebuild_all)
    out = await memory_reindex(vectors=True, backlinks=False)
    assert calls == [True]
    assert out["vectors"] == 7
    assert out["backlinks"] is None


# ─── CLI (--direct path) ───────────────────────────────────────────────

def test_reindex_cli_direct_backlinks_only(
    tmp_brain: Path, runner: CliRunner
) -> None:
    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")

    result = runner.invoke(
        app, ["reindex", "--no-vectors", "--direct", "--json"]
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["vectors"] is None
    assert isinstance(payload["backlinks"], int)


def test_reindex_cli_rejects_empty_run(
    tmp_brain: Path, runner: CliRunner
) -> None:
    result = runner.invoke(
        app, ["reindex", "--no-vectors", "--no-backlinks", "--direct"]
    )
    assert result.exit_code == 2
    assert "nothing to do" in result.stdout


def test_reindex_cli_direct_vectors(
    tmp_brain: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stub rebuild_all so we don't spin up Milvus during the unit test."""
    async def fake_rebuild_all() -> int:
        return 42

    monkeypatch.setattr("mcs.adapters.search.rebuild_all", fake_rebuild_all)
    result = runner.invoke(
        app, ["reindex", "--no-backlinks", "--direct", "--json"]
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["vectors"] == 42
    assert payload["backlinks"] is None


def test_reindex_cli_human_output(
    tmp_brain: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_rebuild_all() -> int:
        return 3

    monkeypatch.setattr("mcs.adapters.search.rebuild_all", fake_rebuild_all)
    result = runner.invoke(app, ["reindex", "--direct"])
    assert result.exit_code == 0, result.stdout
    assert "vectors re-embedded" in result.stdout
    assert "back-links re-derived" in result.stdout
