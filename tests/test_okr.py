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

def test_list_active_default_is_active_only(tmp_brain: Path) -> None:
    """Default filter shows ONLY active Objectives — achieved/paused/abandoned
    are hidden unless the caller opts in explicitly."""
    a = create_objective(slug="a", quarter="2026-Q2", domain="ml")
    b = create_objective(slug="b", quarter="2026-Q2", domain="ml")
    c = create_objective(slug="c", quarter="2026-Q2", domain="ml")
    update_objective(b.id, status="paused")
    update_objective(c.id, status="achieved")

    ids = {o.id for o in list_active()}
    assert ids == {a.id}


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


# ─── cascade on close ──────────────────────────────────────────────────

def test_achieved_cascades_remaining_krs_to_achieved(tmp_brain: Path) -> None:
    from mcs.adapters.okr import update_objective
    obj = create_objective(slug="c-a", quarter="2026-Q2", domain="ml")
    k_done = create_kr(obj.id, text="already done", status="achieved", current=1, target=1)
    k_progress = create_kr(obj.id, text="mid-flight", status="in_progress")
    k_pending = create_kr(obj.id, text="not yet", status="pending")

    update_objective(obj.id, status="achieved")

    reloaded = get(obj.id)
    status_by_id = {k.id: k.status for k in reloaded.krs}
    assert status_by_id[k_done.id] == "achieved"       # unchanged
    assert status_by_id[k_progress.id] == "achieved"   # cascaded
    assert status_by_id[k_pending.id] == "achieved"    # cascaded


def test_abandoned_cascades_to_abandoned(tmp_brain: Path) -> None:
    from mcs.adapters.okr import update_objective
    obj = create_objective(slug="c-b", quarter="2026-Q2", domain="ml")
    k_done = create_kr(obj.id, text="done", status="achieved", current=1, target=1)
    k_mid = create_kr(obj.id, text="mid", status="in_progress")

    update_objective(obj.id, status="abandoned")

    reloaded = get(obj.id)
    status_by_id = {k.id: k.status for k in reloaded.krs}
    assert status_by_id[k_done.id] == "achieved"       # terminal untouched
    assert status_by_id[k_mid.id] == "abandoned"


def test_paused_does_not_cascade(tmp_brain: Path) -> None:
    from mcs.adapters.okr import update_objective
    obj = create_objective(slug="c-p", quarter="2026-Q2", domain="ml")
    k = create_kr(obj.id, text="keep", status="in_progress")
    update_objective(obj.id, status="paused")
    reloaded = get(obj.id)
    assert reloaded.krs[0].status == "in_progress"  # unchanged


def test_cascade_skips_terminal_krs(tmp_brain: Path) -> None:
    """Already-missed KRs should not be forced to 'achieved'."""
    from mcs.adapters.okr import update_objective
    obj = create_objective(slug="c-t", quarter="2026-Q2", domain="ml")
    k_missed = create_kr(obj.id, text="missed", status="missed")
    k_pending = create_kr(obj.id, text="pending", status="pending")
    update_objective(obj.id, status="achieved")
    reloaded = get(obj.id)
    by = {k.id: k.status for k in reloaded.krs}
    assert by[k_missed.id] == "missed"         # terminal, not overwritten
    assert by[k_pending.id] == "achieved"


def test_cascade_only_on_status_transition(tmp_brain: Path) -> None:
    """Setting status=active again on an active objective does nothing."""
    from mcs.adapters.okr import update_objective
    obj = create_objective(slug="c-n", quarter="2026-Q2", domain="ml")
    k = create_kr(obj.id, text="k", status="in_progress")
    update_objective(obj.id, status="active")   # no change
    assert get(obj.id).krs[0].status == "in_progress"


def test_kr_status_accepts_abandoned(tmp_brain: Path) -> None:
    from mcs.adapters.okr import update_kr
    obj = create_objective(slug="c-d", quarter="2026-Q2", domain="ml")
    k = create_kr(obj.id, text="x", status="in_progress")
    updated = update_kr(k.id, status="abandoned")
    assert updated.status == "abandoned"


# ─── auto-transition on update_kr ──────────────────────────────────────

def test_update_kr_auto_promotes_to_achieved_when_target_met(
    tmp_brain: Path,
) -> None:
    obj = create_objective(slug="p-ach", quarter="2026-Q2", domain="ml")
    k = create_kr(obj.id, text="do 1 thing", target=1, current=0, status="pending")
    out = update_kr(k.id, current=1)     # no explicit status
    assert out.status == "achieved"
    assert out.current == 1.0


def test_update_kr_auto_promotes_to_in_progress_on_nonzero_current(
    tmp_brain: Path,
) -> None:
    obj = create_objective(slug="p-ip", quarter="2026-Q2", domain="ml")
    k = create_kr(obj.id, text="multi step", target=5, current=0, status="pending")
    out = update_kr(k.id, current=2)
    assert out.status == "in_progress"
    assert out.current == 2.0


def test_update_kr_does_not_regress_terminal_status(tmp_brain: Path) -> None:
    """Current going back to 0 should NOT move a terminal KR back to pending."""
    obj = create_objective(slug="p-noreg", quarter="2026-Q2", domain="ml")
    k = create_kr(obj.id, text="t", target=1, current=1, status="achieved")
    out = update_kr(k.id, current=0)
    assert out.status == "achieved"   # terminal — sticky


def test_update_kr_respects_explicit_status(tmp_brain: Path) -> None:
    """Caller-supplied status wins over auto-transition."""
    obj = create_objective(slug="p-exp", quarter="2026-Q2", domain="ml")
    k = create_kr(obj.id, text="t", target=1, current=0, status="pending")
    # User hits the target but marks missed instead of achieved.
    out = update_kr(k.id, current=1, status="missed")
    assert out.status == "missed"


def test_update_kr_no_current_change_no_auto_transition(tmp_brain: Path) -> None:
    obj = create_objective(slug="p-nochg", quarter="2026-Q2", domain="ml")
    k = create_kr(obj.id, text="t", target=1, current=0, status="pending")
    out = update_kr(k.id, text="renamed")    # only text — status stays pending
    assert out.status == "pending"


# ─── current_quarter helper ────────────────────────────────────────────

# ─── KR agent spawn / find ──────────────────────────────────────────────

def test_spawn_kr_agent_writes_skill_md(
    tmp_brain: Path, tmp_path: Path, monkeypatch
) -> None:
    """spawn writes SKILL.md at skills/objectives/<dashed-kr-id>/."""
    from mcs import config as cfg
    from mcs.adapters import okr as okr_mod
    from mcs.adapters.okr import spawn_kr_agent
    # Redirect repo_root to a clean tmp path so the real repo isn't polluted.
    root = tmp_path / "repo"
    root.mkdir()
    orig = cfg.load_settings

    def fake():
        return _with_root(orig(), root)

    monkeypatch.setattr(okr_mod, "load_settings", fake)

    obj = create_objective(slug="agent-spawn", quarter="2026-Q2", domain="ml")
    kr = create_kr(obj.id, text="mock interview 3회", target=3, current=0)

    path = spawn_kr_agent(kr.id, acceptance_criteria=["첫 번째 조건", "두 번째 조건"])
    assert path.exists()
    assert path.parent.name == "2026-Q2-agent-spawn-kr-1"
    assert path.parent.parent == root / "skills" / "objectives"

    post = frontmatter.load(path)
    meta = post.metadata or {}
    assert meta["name"] == "2026-Q2-agent-spawn-kr-1"
    assert meta["metadata"]["mcs"]["kr_id"] == kr.id
    assert meta["metadata"]["mcs"]["parent_objective"] == obj.id
    assert "첫 번째 조건" in post.content
    assert "mock interview 3회" in post.content


def test_spawn_kr_agent_rejects_duplicate_without_overwrite(
    tmp_brain: Path, tmp_path: Path, monkeypatch
) -> None:
    from mcs import config as cfg
    from mcs.adapters.okr import OKRError, spawn_kr_agent
    root = tmp_path / "repo"
    root.mkdir()
    from mcs.adapters import okr as okr_mod
    orig = cfg.load_settings
    monkeypatch.setattr(okr_mod, "load_settings", lambda: _with_root(orig(), root))

    obj = create_objective(slug="dup", quarter="2026-Q2", domain="ml")
    kr = create_kr(obj.id, text="x")
    spawn_kr_agent(kr.id)
    with pytest.raises(OKRError, match="already exists"):
        spawn_kr_agent(kr.id)
    # overwrite=True succeeds
    spawn_kr_agent(kr.id, overwrite=True)


def test_spawn_kr_agent_missing_kr_raises(
    tmp_brain: Path, tmp_path: Path, monkeypatch
) -> None:
    from mcs import config as cfg
    from mcs.adapters.okr import OKRNotFound, spawn_kr_agent
    root = tmp_path / "repo"
    root.mkdir()
    from mcs.adapters import okr as okr_mod
    orig = cfg.load_settings
    monkeypatch.setattr(okr_mod, "load_settings", lambda: _with_root(orig(), root))
    with pytest.raises(OKRNotFound):
        spawn_kr_agent("2026-Q2-no-such.kr-1")


def test_find_kr_agent_returns_path_for_existing(
    tmp_brain: Path, tmp_path: Path, monkeypatch
) -> None:
    from mcs import config as cfg
    from mcs.adapters.okr import find_kr_agent, spawn_kr_agent
    root = tmp_path / "repo"
    root.mkdir()
    from mcs.adapters import okr as okr_mod
    orig = cfg.load_settings
    monkeypatch.setattr(okr_mod, "load_settings", lambda: _with_root(orig(), root))

    obj = create_objective(slug="find", quarter="2026-Q2", domain="ml")
    kr = create_kr(obj.id, text="y")
    assert find_kr_agent(kr.id) is None    # before spawn
    spawn_kr_agent(kr.id)
    found = find_kr_agent(kr.id)
    assert found is not None
    assert found.name == "SKILL.md"


def test_find_kr_agent_returns_none_for_unknown(
    tmp_brain: Path, tmp_path: Path, monkeypatch
) -> None:
    from mcs import config as cfg
    from mcs.adapters.okr import find_kr_agent
    root = tmp_path / "repo"
    root.mkdir()
    from mcs.adapters import okr as okr_mod
    orig = cfg.load_settings
    monkeypatch.setattr(okr_mod, "load_settings", lambda: _with_root(orig(), root))
    assert find_kr_agent("2026-Q2-nope.kr-1") is None


def _with_root(settings, root: Path):
    """Test helper — mutate settings.repo_root in place."""
    settings.repo_root = root
    return settings


def test_current_quarter_computes_from_kst_month() -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from mcs.adapters.okr import current_quarter

    kst = ZoneInfo("Asia/Seoul")
    assert current_quarter(datetime(2026, 1, 5, tzinfo=kst)) == "2026-Q1"
    assert current_quarter(datetime(2026, 4, 23, tzinfo=kst)) == "2026-Q2"
    assert current_quarter(datetime(2026, 7, 1, tzinfo=kst)) == "2026-Q3"
    assert current_quarter(datetime(2026, 12, 31, tzinfo=kst)) == "2026-Q4"
