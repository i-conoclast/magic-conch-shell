"""Tests for `mcs retro` orchestration — Phase 10.3 inbox-approve wiring."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from typer.testing import CliRunner

from mcs.adapters.hermes_client import (
    inbox_approve_session_name,
    retro_session_name,
)
from mcs.cli import app
from mcs.commands import retro as retro_mod


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ─── session names ─────────────────────────────────────────────────────

def test_inbox_approve_session_name_pinned_when_date_given() -> None:
    assert inbox_approve_session_name("2026-05-01") == "inbox-approve-2026-05-01"


def test_inbox_approve_session_name_uses_today_kst() -> None:
    fake_now = datetime(2026, 5, 1, 22, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    assert (
        inbox_approve_session_name(now=fake_now)
        == "inbox-approve-2026-05-01"
    )


def test_session_names_share_date_for_same_invocation() -> None:
    fake_now = datetime(2026, 5, 1, 22, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    assert retro_session_name(now=fake_now).endswith("2026-05-01")
    assert inbox_approve_session_name(now=fake_now).endswith("2026-05-01")


# ─── empty-inbox heuristic ─────────────────────────────────────────────

@pytest.mark.parametrize(
    "reply",
    [
        "no entity drafts.",
        "No Entity Drafts",
        "처리 완료. 인박스 비었음.",
        "인박스 0건. 종료.",
    ],
)
def test_looks_empty_inbox_recognises_marker(reply: str) -> None:
    assert retro_mod._looks_empty_inbox(reply) is True


@pytest.mark.parametrize(
    "reply",
    [
        "인박스 3건:\n1. people/jane-smith ...",
        "✓ 1 confirmed, ⊘ 1 rejected",
        "",
    ],
)
def test_looks_empty_inbox_does_not_misfire(reply: str) -> None:
    assert retro_mod._looks_empty_inbox(reply) is False


# ─── CLI flag wiring ───────────────────────────────────────────────────

def test_retro_help_lists_skip_inbox(runner: CliRunner) -> None:
    result = runner.invoke(app, ["retro", "--help"])
    assert result.exit_code == 0
    assert "--skip-inbox" in result.stdout


def test_retro_skip_all_runs_only_phase_a(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    """--skip-inbox --skip-sync leaves only the narrative phase."""
    calls: list[str] = []

    monkeypatch.setattr(
        retro_mod, "_run_retro_phase", lambda d, r: calls.append("retro")
    )
    monkeypatch.setattr(
        retro_mod, "_run_inbox_approve_phase", lambda d: calls.append("inbox-approve")
    )
    monkeypatch.setattr(retro_mod, "_run_sync_phase", lambda d: calls.append("sync"))

    result = runner.invoke(
        app, ["retro", "--skip-inbox", "--skip-sync"]
    )
    assert result.exit_code == 0
    assert calls == ["retro"]


def test_retro_default_runs_all_three_phases(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(retro_mod, "_run_retro_phase", lambda d, r: calls.append("retro"))
    monkeypatch.setattr(
        retro_mod, "_run_inbox_approve_phase", lambda d: calls.append("inbox-approve")
    )
    monkeypatch.setattr(retro_mod, "_run_sync_phase", lambda d: calls.append("sync"))

    result = runner.invoke(app, ["retro", "2026-05-01"])
    assert result.exit_code == 0
    assert calls == ["retro", "inbox-approve", "sync"]


def test_retro_skip_inbox_keeps_sync(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(retro_mod, "_run_retro_phase", lambda d, r: calls.append("retro"))
    monkeypatch.setattr(
        retro_mod, "_run_inbox_approve_phase", lambda d: calls.append("inbox-approve")
    )
    monkeypatch.setattr(retro_mod, "_run_sync_phase", lambda d: calls.append("sync"))

    result = runner.invoke(app, ["retro", "--skip-inbox"])
    assert result.exit_code == 0
    assert calls == ["retro", "sync"]


# ─── _run_inbox_approve_phase auto-exit on empty inbox ─────────────────

def test_inbox_approve_phase_auto_exits_when_inbox_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One mocked Hermes call returning the empty marker must close the REPL."""
    call_count = {"n": 0}

    async def fake_run_skill(*, skill, opener, conversation, timeout):
        call_count["n"] += 1
        return {"text": "no entity drafts.", "raw": {}}

    monkeypatch.setattr(retro_mod, "run_skill", fake_run_skill)

    # Should return without prompting for input — call count = 1.
    retro_mod._run_inbox_approve_phase("2026-05-01")
    assert call_count["n"] == 1
