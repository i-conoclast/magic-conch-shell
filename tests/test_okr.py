"""Tests for adapters/okr.py — folder-per-objective, KR-per-file."""
from __future__ import annotations

from pathlib import Path

import frontmatter
import pytest

from mcs.adapters.okr import (
    OKRError,
    OKRNotFound,
    create_kr,
    create_objective,
    get,
    get_kr,
    list_active,
    update_kr,
    update_objective,
)


# ─── create_objective ──────────────────────────────────────────────────

def test_create_objective_writes_file(tmp_brain: Path) -> None:
    obj = create_objective(
        slug="career-mle-role",
        quarter="2026-Q2",
        domain="career",
        confidence=0.7,
        entities=["companies/anthropic"],
        body="Why and strategy here.",
    )
    assert obj.id == "2026-Q2-career-mle-role"
    assert obj.path.exists()
    assert obj.folder.is_dir()

    meta = frontmatter.load(obj.path).metadata
    assert meta["type"] == "objective"
    assert meta["quarter"] == "2026-Q2"
    assert meta["domain"] == "career"
    assert meta["confidence"] == 0.7
    assert "companies/anthropic" in meta["entities"]


def test_create_objective_rejects_bad_quarter(tmp_brain: Path) -> None:
    with pytest.raises(OKRError, match="quarter"):
        create_objective(slug="x", quarter="2026-Q5", domain="career")


def test_create_objective_rejects_unknown_domain(tmp_brain: Path) -> None:
    with pytest.raises(OKRError, match="domain"):
        create_objective(slug="x", quarter="2026-Q2", domain="nonsense")


def test_create_objective_rejects_duplicate_slug(tmp_brain: Path) -> None:
    create_objective(slug="dup", quarter="2026-Q2", domain="ml")
    with pytest.raises(OKRError, match="already exists"):
        create_objective(slug="dup", quarter="2026-Q2", domain="ml")


# ─── create_kr / get / get_kr ──────────────────────────────────────────

def test_create_kr_and_round_trip(tmp_brain: Path) -> None:
    obj = create_objective(slug="mle", quarter="2026-Q2", domain="career")
    kr = create_kr(
        obj.id,
        text="Anthropic MLE 1차 통과",
        target=1,
        current=0,
        unit="count",
        status="in_progress",
    )
    assert kr.id == f"{obj.id}.kr-1"
    assert kr.parent == obj.id
    assert kr.path.exists()

    # A second KR auto-increments to kr-2.
    kr2 = create_kr(obj.id, text="2차 offer", target=1)
    assert kr2.id.endswith(".kr-2")

    # get() loads the objective with both KRs attached.
    loaded = get(obj.id)
    assert len(loaded.krs) == 2
    assert {k.id for k in loaded.krs} == {kr.id, kr2.id}

    # get_kr() directly.
    fetched = get_kr(kr.id)
    assert fetched.text == "Anthropic MLE 1차 통과"


def test_create_kr_missing_parent_raises(tmp_brain: Path) -> None:
    with pytest.raises(OKRNotFound):
        create_kr("2026-Q2-no-such-objective", text="whatever")


def test_create_kr_rejects_bad_status(tmp_brain: Path) -> None:
    obj = create_objective(slug="ml", quarter="2026-Q2", domain="ml")
    with pytest.raises(OKRError, match="kr status"):
        create_kr(obj.id, text="x", status="hopeful")


# ─── update_kr ─────────────────────────────────────────────────────────

def test_update_kr_fields_and_updated_at(tmp_brain: Path) -> None:
    obj = create_objective(slug="u", quarter="2026-Q2", domain="ml")
    kr = create_kr(obj.id, text="initial", target=5, current=0)
    original_updated = kr.updated_at

    updated = update_kr(kr.id, current=3, status="in_progress")
    assert updated.current == 3
    assert updated.status == "in_progress"
    assert updated.updated_at != original_updated  # re-stamped


def test_update_kr_unknown_field_raises(tmp_brain: Path) -> None:
    obj = create_objective(slug="u2", quarter="2026-Q2", domain="ml")
    kr = create_kr(obj.id, text="t")
    with pytest.raises(OKRError, match="unknown kr field"):
        update_kr(kr.id, nonsense="x")


def test_update_kr_missing_raises(tmp_brain: Path) -> None:
    with pytest.raises(OKRNotFound):
        update_kr("2026-Q2-missing.kr-7", current=1)


def test_update_kr_touches_parent_updated_at(tmp_brain: Path) -> None:
    obj = create_objective(slug="touch", quarter="2026-Q2", domain="ml")
    orig_parent_updated = obj.updated_at
    kr = create_kr(obj.id, text="t")
    # Sleep-free: create_kr already stamped parent, now re-touch via update.
    update_kr(kr.id, current=1)
    reloaded = get(obj.id)
    assert reloaded.updated_at >= orig_parent_updated


# ─── update_objective ──────────────────────────────────────────────────

def test_update_objective_status(tmp_brain: Path) -> None:
    obj = create_objective(slug="obj", quarter="2026-Q2", domain="ml")
    out = update_objective(obj.id, status="achieved", confidence=0.95)
    assert out.status == "achieved"
    assert out.confidence == 0.95


def test_update_objective_rejects_bad_status(tmp_brain: Path) -> None:
    obj = create_objective(slug="s", quarter="2026-Q2", domain="ml")
    with pytest.raises(OKRError):
        update_objective(obj.id, status="on_fire")


# ─── list_active ───────────────────────────────────────────────────────

def test_list_active_includes_active_and_achieved_only(tmp_brain: Path) -> None:
    a = create_objective(slug="a", quarter="2026-Q2", domain="ml")
    b = create_objective(slug="b", quarter="2026-Q2", domain="ml")
    c = create_objective(slug="c", quarter="2026-Q2", domain="ml")
    update_objective(b.id, status="paused")
    update_objective(c.id, status="achieved")

    ids = {o.id for o in list_active()}
    assert a.id in ids
    assert c.id in ids       # achieved still shown (recent wins)
    assert b.id not in ids   # paused hidden


def test_list_active_quarter_filter(tmp_brain: Path) -> None:
    create_objective(slug="q2", quarter="2026-Q2", domain="ml")
    create_objective(slug="q3", quarter="2026-Q3", domain="ml")
    only_q2 = list_active("2026-Q2")
    assert {o.quarter for o in only_q2} == {"2026-Q2"}


def test_list_active_empty_when_no_root(tmp_brain: Path) -> None:
    assert list_active() == []


def test_list_active_all_statuses_includes_paused_and_abandoned(tmp_brain: Path) -> None:
    a = create_objective(slug="a", quarter="2026-Q2", domain="ml")
    b = create_objective(slug="b", quarter="2026-Q2", domain="ml")
    c = create_objective(slug="c", quarter="2026-Q2", domain="ml")
    from mcs.adapters.okr import update_objective
    update_objective(b.id, status="paused")
    update_objective(c.id, status="abandoned")

    ids_all = {o.id for o in list_active(statuses=["all"])}
    assert {a.id, b.id, c.id} == ids_all


def test_list_active_explicit_status_subset(tmp_brain: Path) -> None:
    a = create_objective(slug="a", quarter="2026-Q2", domain="ml")
    b = create_objective(slug="b", quarter="2026-Q2", domain="ml")
    from mcs.adapters.okr import update_objective
    update_objective(b.id, status="paused")

    only_paused = list_active(statuses=["paused"])
    assert [o.id for o in only_paused] == [b.id]


def test_list_active_domain_filter(tmp_brain: Path) -> None:
    a = create_objective(slug="a", quarter="2026-Q2", domain="ml")
    b = create_objective(slug="b", quarter="2026-Q2", domain="career")
    result = list_active(domain="career")
    assert [o.id for o in result] == [b.id]
