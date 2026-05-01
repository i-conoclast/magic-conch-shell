"""Unit tests for mcs.adapters.skill_labeler (Phase 12.3)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from mcs.adapters import skill_labeler as labeler
from mcs.adapters import skill_suggestion as ss
from mcs.adapters.skill_detector import SkillCandidate


KST = ZoneInfo("Asia/Seoul")


# ─── helpers ───────────────────────────────────────────────────────────

def _candidate(seed: str = "capture:signals/2026-04-28-a") -> SkillCandidate:
    return SkillCandidate(
        seed_id=seed,
        member_ids=[seed, "capture:signals/2026-04-29-b"],
        sample_texts=[
            "오늘 점심 김밥 / 짜장 / 햄버거 ...",
            "어제 점심 비빔밥 / 김밥 ...",
        ],
        avg_score=0.82,
        earliest=datetime(2026, 4, 28, 12, 0, tzinfo=KST),
        latest=datetime(2026, 5, 1, 12, 0, tzinfo=KST),
        edge_count=2,
        payload={"source_types": ["capture"], "domains": ["general"]},
    )


def _fake_run(response_text: str):
    """Return a run_fn that always responds with `response_text`."""

    async def _fn(**kwargs):
        return {"text": response_text}

    return _fn


# ─── format_candidate_opener ───────────────────────────────────────────

def test_format_opener_includes_required_fields() -> None:
    c = _candidate()
    opener = labeler.format_candidate_opener(c)
    assert "cluster_seed: capture:signals/2026-04-28-a" in opener
    assert "member_count: 2" in opener
    assert "time_spread_days: 3.00" in opener
    assert "avg_score: 0.820" in opener
    assert "domains: [general]" in opener
    assert "1. 오늘 점심" in opener
    assert "2. 어제 점심" in opener


def test_format_opener_collapses_multiline_excerpts() -> None:
    c = _candidate()
    c.sample_texts = ["line one\n\nline two\n  line three"]
    opener = labeler.format_candidate_opener(c)
    assert "line one line two line three" in opener


# ─── parse_label_response ──────────────────────────────────────────────

def test_parse_plain_json() -> None:
    raw = '{"slug": "lunch-log", "name": "Lunch Log", "summary": "x", "body": "y"}'
    parsed = labeler.parse_label_response(raw)
    assert parsed["slug"] == "lunch-log"


def test_parse_fenced_json() -> None:
    raw = "Here you go:\n```json\n{\"slug\": \"lunch-log\"}\n```"
    parsed = labeler.parse_label_response(raw)
    assert parsed["slug"] == "lunch-log"


def test_parse_json_with_leading_prose() -> None:
    raw = "Looks like a lunch pattern.\n{\"slug\": \"lunch-log\", \"name\": \"x\"}"
    parsed = labeler.parse_label_response(raw)
    assert parsed["slug"] == "lunch-log"


def test_parse_null_slug_response() -> None:
    raw = '{"slug": null, "reason": "not coherent"}'
    parsed = labeler.parse_label_response(raw)
    assert parsed["slug"] is None
    assert parsed["reason"] == "not coherent"


def test_parse_empty_raises() -> None:
    with pytest.raises(ValueError):
        labeler.parse_label_response("")


def test_parse_no_json_raises() -> None:
    with pytest.raises(ValueError):
        labeler.parse_label_response("no json here, just words")


# ─── label_candidate happy path ────────────────────────────────────────

@pytest.mark.asyncio
async def test_label_candidate_creates_draft(
    tmp_brain: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LLM returns a clean JSON; draft lands in .brain/skill-suggestions/."""
    response = json.dumps({
        "slug": "lunch-log",
        "name": "Lunch Log",
        "summary": "daily lunch tracking",
        "body": "## 트리거\n\n매일 점심.\n",
    })
    out = await labeler.label_candidate(_candidate(), run_fn=_fake_run(response))

    assert out.status == "created"
    assert out.slug == "lunch-log"

    sug = ss.resolve("lunch-log")
    assert sug.name == "Lunch Log"
    assert sug.summary == "daily lunch tracking"
    assert sug.meta.get("detected_via") == "ann-cluster"
    assert sug.meta.get("member_count") == 2


@pytest.mark.asyncio
async def test_label_candidate_skip_when_llm_returns_null(tmp_brain: Path) -> None:
    response = json.dumps({"slug": None, "reason": "samples differ"})
    out = await labeler.label_candidate(_candidate(), run_fn=_fake_run(response))
    assert out.status == "skipped-by-llm"
    assert out.reason == "samples differ"
    assert ss.list_drafts() == []


# ─── error paths ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_label_candidate_error_on_unparseable_response(tmp_brain: Path) -> None:
    out = await labeler.label_candidate(
        _candidate(), run_fn=_fake_run("not even close to json")
    )
    assert out.status == "error"
    assert "no JSON object" in (out.reason or "")


@pytest.mark.asyncio
async def test_label_candidate_swallows_run_skill_exception(tmp_brain: Path) -> None:
    async def boom(**kwargs):
        raise RuntimeError("hermes is sleeping")

    out = await labeler.label_candidate(_candidate(), run_fn=boom)
    assert out.status == "error"
    assert "hermes is sleeping" in (out.reason or "")


@pytest.mark.asyncio
async def test_label_candidate_skip_when_draft_already_exists(tmp_brain: Path) -> None:
    # Pre-stage a draft with the slug the LLM is going to propose.
    ss.create_draft(slug="lunch-log", name="Lunch Log")

    response = json.dumps({"slug": "lunch-log", "name": "Lunch Log"})
    out = await labeler.label_candidate(_candidate(), run_fn=_fake_run(response))
    assert out.status == "skipped-existing"
    assert out.slug == "lunch-log"


# ─── batch ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_label_candidates_processes_all(tmp_brain: Path) -> None:
    c1 = _candidate(seed="capture:signals/c1")
    c2 = _candidate(seed="capture:signals/c2")
    response = json.dumps({"slug": "x-skill", "name": "X"})

    # Per-candidate run_fn that returns the same response (idempotency
    # already covered by skipped-existing flow).
    out = await labeler.label_candidates([c1, c2], run_fn=_fake_run(response))
    statuses = [o.status for o in out]
    assert statuses[0] == "created"
    # Second one collides on the same slug → skipped.
    assert statuses[1] in {"skipped-existing", "error"}
