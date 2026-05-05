"""Tests for `mcs doctor` CLI (FR-I1 / F-80)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mcs.cli import app
from mcs.commands import doctor as doc


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def stub_no_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default = nothing listening + no leaked ~/.hermes/.env values."""
    monkeypatch.setattr(doc, "_port_open", lambda host, port, timeout=0.3: False)
    # The user's real ~/.hermes/.env can flip webhook flags / set Notion
    # creds for the test process; block that fallback so checks see only
    # the in-test environment.
    monkeypatch.setattr("mcs.config._env_or_hermes_env", lambda key: None)


def test_doctor_json_payload_lists_all_checks(
    tmp_brain: Path, runner: CliRunner, stub_no_ports: None
) -> None:
    result = runner.invoke(app, ["doctor", "--json"])
    # Without daemon/gateway, no FAILs are expected (just warns).
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    names = [r["name"] for r in payload]
    for expected in [
        "brain dir",
        "milvus db",
        "daemon",
        "hermes gateway",
        "hermes webhook",
        "hermes api key",
        "notion creds",
    ]:
        assert expected in names


def test_doctor_brain_dir_ok(tmp_brain: Path, stub_no_ports: None) -> None:
    r = doc._check_brain_paths()
    assert r.status == "ok"
    assert "brain" in r.detail


def test_doctor_brain_dir_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No brain/ directory under cwd → FAIL."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCS_REPO_ROOT", str(tmp_path))
    r = doc._check_brain_paths()
    assert r.status == "fail"
    assert "missing" in r.detail


def test_doctor_milvus_db_warn_when_absent(tmp_brain: Path) -> None:
    r = doc._check_milvus_db()
    assert r.status == "warn"


def test_doctor_milvus_db_ok_when_present(tmp_brain: Path) -> None:
    db = tmp_brain.parent / ".brain" / "memsearch.db"
    db.write_bytes(b"x" * 2048)
    r = doc._check_milvus_db()
    assert r.status == "ok"
    assert "MB" in r.detail


def test_doctor_daemon_warn_when_not_running(
    tmp_brain: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(doc, "_port_open", lambda *a, **kw: False)
    r = doc._check_daemon()
    assert r.status == "warn"


def test_doctor_daemon_fail_when_pid_stale(
    tmp_brain: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_file = tmp_brain.parent / ".brain" / "daemon.pid"
    pid_file.write_text("99999\n", encoding="utf-8")
    monkeypatch.setattr(doc, "_port_open", lambda *a, **kw: False)
    r = doc._check_daemon()
    assert r.status == "fail"
    assert "stale" in r.detail


def test_doctor_daemon_ok_when_listening(
    tmp_brain: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_file = tmp_brain.parent / ".brain" / "daemon.pid"
    pid_file.write_text("12345\n", encoding="utf-8")
    monkeypatch.setattr(doc, "_port_open", lambda *a, **kw: True)
    r = doc._check_daemon()
    assert r.status == "ok"
    assert "12345" in r.detail


def test_doctor_notion_creds_warn_when_unset(
    tmp_brain: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for k in [
        "MCS_NOTION_TOKEN",
        "MCS_NOTION_OKR_MASTER_DB",
        "MCS_NOTION_KR_TRACKER_DB",
        "MCS_NOTION_DAILY_TASKS_DB",
        "MCS_NOTION_CAPTURES_DB",
    ]:
        monkeypatch.delenv(k, raising=False)
    # Also block ~/.hermes/.env fallback so we test the unset path cleanly.
    monkeypatch.setattr(
        "mcs.config._env_or_hermes_env", lambda key: None
    )
    r = doc._check_notion_creds(probe=False)
    assert r.status == "warn"


def test_doctor_hermes_webhook_ok_when_disabled(
    tmp_brain: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "mcs.config._env_or_hermes_env", lambda key: None
    )
    r = doc._check_hermes_webhook()
    assert r.status == "ok"
    assert "off" in r.detail or "no webhook" in r.detail


def test_doctor_exit_code_one_on_fail(
    tmp_brain: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stale daemon pid forces a FAIL → exit 1."""
    pid_file = tmp_brain.parent / ".brain" / "daemon.pid"
    pid_file.write_text("99999\n", encoding="utf-8")
    monkeypatch.setattr(doc, "_port_open", lambda *a, **kw: False)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
