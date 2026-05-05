"""Tests for `mcs day` CLI (FR-B3 / F-12)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mcs.adapters.memory import capture, upsert_daily_section
from mcs.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _stamp_created_at(path: Path, iso: str) -> None:
    """Rewrite a capture's `created_at` so list_captures_by_date can match a fixed date."""
    import frontmatter

    post = frontmatter.load(path)
    meta = dict(post.metadata or {})
    meta["created_at"] = iso
    path.write_text(
        frontmatter.dumps(frontmatter.Post(post.content or "", **meta)) + "\n",
        encoding="utf-8",
    )


def test_day_direct_renders_captures_and_daily(
    tmp_brain: Path, runner: CliRunner
) -> None:
    date = "2026-04-22"
    cap = capture(text="아침 한 줄", domain="career")
    _stamp_created_at(cap.path, f"{date}T08:30:00+09:00")
    upsert_daily_section(date, "Morning Brief", "오늘은 면접 준비.")

    result = runner.invoke(app, ["day", date, "--direct"])
    assert result.exit_code == 0, result.stdout
    assert date in result.stdout
    assert "Morning Brief" in result.stdout
    assert "아침 한 줄" in result.stdout
    assert "career" in result.stdout


def test_day_direct_json_payload(tmp_brain: Path, runner: CliRunner) -> None:
    date = "2026-04-22"
    cap = capture(text="기록")
    _stamp_created_at(cap.path, f"{date}T11:00:00+09:00")

    result = runner.invoke(app, ["day", date, "--direct", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["date"] == date
    assert payload["daily"]["exists"] is False
    assert len(payload["captures"]) == 1
    assert payload["captures"][0]["excerpt"].startswith("기록")


def test_day_direct_no_records(tmp_brain: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["day", "2026-04-22", "--direct"])
    assert result.exit_code == 0, result.stdout
    assert "no captures on this date" in result.stdout
    assert "no daily/ entry yet" in result.stdout


def test_day_invalid_date(tmp_brain: Path, runner: CliRunner) -> None:
    result = runner.invoke(app, ["day", "2026/04/22", "--direct"])
    assert result.exit_code == 2
    assert "YYYY-MM-DD" in result.stdout


def test_day_domain_filter(tmp_brain: Path, runner: CliRunner) -> None:
    date = "2026-04-22"
    a = capture(text="career memo", domain="career")
    b = capture(text="finance memo", domain="finance")
    _stamp_created_at(a.path, f"{date}T09:00:00+09:00")
    _stamp_created_at(b.path, f"{date}T10:00:00+09:00")

    result = runner.invoke(
        app, ["day", date, "--direct", "--domain", "career", "--json"]
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert len(payload["captures"]) == 1
    assert payload["captures"][0]["domain"] == "career"


def test_day_default_is_today(tmp_brain: Path, runner: CliRunner) -> None:
    """No arg → uses KST today; just smoke-test it doesn't blow up."""
    result = runner.invoke(app, ["day", "--direct", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    # Date format check, not the exact value.
    assert len(payload["date"]) == 10 and payload["date"].count("-") == 2
