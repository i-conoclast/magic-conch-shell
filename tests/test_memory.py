"""Unit tests for mcs.adapters.memory.capture() and supplement_frontmatter()."""
from __future__ import annotations

from pathlib import Path

import frontmatter
import pytest

from mcs.adapters.memory import (
    MemoAmbiguous,
    MemoNotFound,
    add_okr_link,
    add_task_link,
    capture,
    daily_file_path,
    list_captures_by_date,
    load_memo,
    resolve_memo,
    supplement_frontmatter,
    read_daily,
    upsert_daily_section,
)


def _read_meta(path: Path) -> dict:
    return frontmatter.load(path).metadata


def test_signal_when_no_domain(tmp_brain: Path) -> None:
    result = capture(text="가벼운 한 줄")

    assert result.path.is_relative_to(tmp_brain / "signals")
    assert result.type == "signal"
    assert result.domain is None

    meta = _read_meta(result.path)
    assert meta["type"] == "signal"
    assert meta["domain"] is None


def test_note_when_domain_is_set(tmp_brain: Path) -> None:
    result = capture(text="면접 준비", domain="career")

    assert result.path.is_relative_to(tmp_brain / "domains" / "career")
    assert result.type == "note"
    assert result.domain == "career"

    meta = _read_meta(result.path)
    assert meta["type"] == "note"
    assert meta["domain"] == "career"


def test_invalid_domain_raises(tmp_brain: Path) -> None:
    with pytest.raises(ValueError, match="Unknown domain"):
        capture(text="...", domain="not-a-real-domain")


def test_collision_suffix_and_id_match_filename(tmp_brain: Path) -> None:
    """Day 3 regression: `-2` suffix must propagate to frontmatter `id`."""
    first = capture(text="one", title="shared-slug")
    second = capture(text="two", title="shared-slug")

    assert first.path != second.path
    assert second.path.stem.endswith("-2")
    assert second.id == second.path.stem
    assert _read_meta(second.path)["id"] == second.path.stem


def test_many_collisions_increment(tmp_brain: Path) -> None:
    ids = {capture(text=str(i), title="busy").path.stem for i in range(4)}
    # First is plain slug, rest are -2, -3, -4.
    assert len(ids) == 4
    assert any(i.endswith("-2") for i in ids)
    assert any(i.endswith("-3") for i in ids)
    assert any(i.endswith("-4") for i in ids)


def test_title_produces_kebab_slug(tmp_brain: Path) -> None:
    result = capture(text="...", title="Anthropic MLE — 1st round")
    assert "anthropic-mle" in result.path.stem
    assert result.path.stem.endswith("1st-round")


def test_entities_persist_in_frontmatter(tmp_brain: Path) -> None:
    entities = ["people/jane-smith", "companies/anthropic"]
    result = capture(
        text="follow-up 예정",
        domain="career",
        entities=entities,
    )
    meta = _read_meta(result.path)
    assert meta["entities"] == entities


def test_body_written_with_trailing_newline(tmp_brain: Path) -> None:
    result = capture(text="body text")
    raw = result.path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert "body text" in raw


def test_source_field_defaults_to_typed(tmp_brain: Path) -> None:
    result = capture(text="...")
    assert _read_meta(result.path)["source"] == "typed"


def test_source_field_override(tmp_brain: Path) -> None:
    result = capture(text="...", source="file-watcher")
    assert _read_meta(result.path)["source"] == "file-watcher"


# ─── supplement_frontmatter ─────────────────────────────────────────────

def test_supplement_fills_missing_fields_for_signal(tmp_brain: Path) -> None:
    (tmp_brain / "signals").mkdir()
    path = tmp_brain / "signals" / "2026-04-22-raw.md"
    path.write_text("bare body, no yaml\n", encoding="utf-8")

    changed = supplement_frontmatter(path)
    assert changed is True

    meta = _read_meta(path)
    assert meta["id"] == "2026-04-22-raw"
    assert meta["type"] == "signal"
    assert meta["domain"] is None
    assert meta["entities"] == []
    assert meta["source"] == "file-watcher"
    assert "created_at" in meta


def test_supplement_infers_note_from_domain_path(tmp_brain: Path) -> None:
    (tmp_brain / "domains" / "career").mkdir(parents=True)
    path = tmp_brain / "domains" / "career" / "2026-04-22-foo.md"
    path.write_text("career memo\n", encoding="utf-8")

    supplement_frontmatter(path)
    meta = _read_meta(path)
    assert meta["type"] == "note"
    assert meta["domain"] == "career"


def test_supplement_is_idempotent(tmp_brain: Path) -> None:
    (tmp_brain / "signals").mkdir()
    path = tmp_brain / "signals" / "x.md"
    # Phase 9: include matching body_hash so the file is fully supplemented.
    from mcs.adapters.memory import _body_hash
    body = "body\n"
    h = _body_hash(body)
    path.write_text(
        f"---\nid: x\ntype: signal\ndomain: null\nentities: []\n"
        f"created_at: '2026-04-22T00:00:00+09:00'\nsource: typed\n"
        f"body_hash: {h}\n---\n\n{body}",
        encoding="utf-8",
    )

    # All required fields present + hash matches → no rewrite
    assert supplement_frontmatter(path) is False


def test_supplement_preserves_existing_fields(tmp_brain: Path) -> None:
    (tmp_brain / "signals").mkdir()
    path = tmp_brain / "signals" / "x.md"
    # source field missing, but id/type/domain/entities/created_at exist
    path.write_text(
        "---\nid: x\ntype: signal\ndomain: null\nentities: [a]\ncreated_at: '2026-04-22T00:00:00+09:00'\n---\n\nbody\n",
        encoding="utf-8",
    )
    assert supplement_frontmatter(path) is True
    meta = _read_meta(path)
    assert meta["entities"] == ["a"]           # preserved
    assert meta["id"] == "x"                    # preserved
    assert meta["source"] == "file-watcher"     # filled


def test_supplement_ignores_paths_outside_scope(tmp_brain: Path) -> None:
    # brain/daily/ is not in watcher scope — supplement should refuse.
    (tmp_brain / "daily").mkdir()
    path = tmp_brain / "daily" / "foo.md"
    path.write_text("naked\n", encoding="utf-8")
    assert supplement_frontmatter(path) is False


def test_supplement_rejects_unknown_domain(tmp_brain: Path) -> None:
    (tmp_brain / "domains" / "bogus").mkdir(parents=True)
    path = tmp_brain / "domains" / "bogus" / "x.md"
    path.write_text("body\n", encoding="utf-8")
    # Not a whitelisted domain → skip supplementing.
    assert supplement_frontmatter(path) is False


# ─── resolve_memo / load_memo ───────────────────────────────────────────

def test_resolve_bare_slug_in_signals(tmp_brain: Path) -> None:
    r = capture(text="hello", title="demo-slug")
    resolved = resolve_memo(r.path.stem)
    assert resolved == r.path.resolve()


def test_resolve_bare_slug_in_domain(tmp_brain: Path) -> None:
    r = capture(text="note", domain="career", title="demo-slug")
    resolved = resolve_memo(r.path.stem)
    assert resolved == r.path.resolve()


def test_resolve_relative_path(tmp_brain: Path) -> None:
    r = capture(text="x", title="path-form")
    rel = f"signals/{r.path.stem}"
    assert resolve_memo(rel) == r.path.resolve()


def test_resolve_path_with_md_suffix(tmp_brain: Path) -> None:
    r = capture(text="x", title="path-form-md")
    rel = f"signals/{r.path.stem}.md"
    assert resolve_memo(rel) == r.path.resolve()


def test_resolve_path_with_brain_prefix(tmp_brain: Path) -> None:
    r = capture(text="x", title="brain-prefix")
    rel = f"brain/signals/{r.path.stem}.md"
    assert resolve_memo(rel) == r.path.resolve()


def test_resolve_not_found_raises(tmp_brain: Path) -> None:
    with pytest.raises(MemoNotFound):
        resolve_memo("2026-99-99-no-such-memo")


def test_resolve_ambiguous_raises_with_candidates(tmp_brain: Path) -> None:
    # Same slug in two locations — use the stem from the capture so the
    # test stays correct regardless of the calendar day it runs on.
    a = capture(text="in signals", title="dupe")
    b = capture(text="in career", domain="career", title="dupe")
    assert a.path.stem == b.path.stem, "setup: both captures should share a slug"
    with pytest.raises(MemoAmbiguous) as info:
        resolve_memo(a.path.stem)
    assert len(info.value.candidates) == 2
    assert a.path in [p.resolve() for p in info.value.candidates]
    assert b.path in [p.resolve() for p in info.value.candidates]


def test_capture_persists_okrs_frontmatter(tmp_brain: Path) -> None:
    result = capture(
        text="mock interview 1회 완료",
        domain="career",
        entities=["people/jane-smith"],
        okrs=["2026-Q2-career-mle-role.kr-2"],
    )
    meta = _read_meta(result.path)
    assert meta["okrs"] == ["2026-Q2-career-mle-role.kr-2"]


def test_capture_multiple_okrs(tmp_brain: Path) -> None:
    result = capture(
        text="LoRA 3회 + mock interview 연계 작업",
        domain="ml",
        okrs=[
            "2026-Q2-career-mle-role.kr-2",
            "2026-Q2-ml-rag-mastery.kr-1",
        ],
    )
    meta = _read_meta(result.path)
    assert len(meta["okrs"]) == 2


def test_capture_empty_okrs_omits_field(tmp_brain: Path) -> None:
    """`okrs:` key should stay out of frontmatter when no links were given."""
    result = capture(text="just a thought")
    meta = _read_meta(result.path)
    assert "okrs" not in meta


def test_load_memo_parses_frontmatter_and_body(tmp_brain: Path) -> None:
    r = capture(
        text="body line 1\nbody line 2",
        domain="career",
        entities=["people/jane-smith"],
        title="full-load",
    )
    memo = load_memo(r.path.stem)
    assert memo.id == r.path.stem
    assert memo.type == "note"
    assert memo.domain == "career"
    assert memo.entities == ["people/jane-smith"]
    assert "body line 1" in memo.body
    assert memo.source == "typed"


# ─── list_captures_by_date / add_okr_link ──────────────────────────────

def test_list_captures_by_date_filters_to_date(tmp_brain: Path) -> None:
    """Only captures whose created_at starts with the given date are returned."""
    today = capture(text="today signal")
    today_note = capture(text="today note", domain="ml")
    # Force an old capture by rewriting created_at.
    old = capture(text="yesterday signal")
    post = frontmatter.load(old.path)
    meta = dict(post.metadata)
    meta["created_at"] = "2026-04-01T09:00:00+09:00"
    post = frontmatter.Post(post.content, **meta)
    old.path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")

    # Today's date from the just-created signal
    today_meta = frontmatter.load(today.path).metadata
    today_date = str(today_meta["created_at"])[:10]

    rows = list_captures_by_date(today_date)
    ids = {r.id for r in rows}
    assert today.path.stem in ids
    assert today_note.path.stem in ids
    assert old.path.stem not in ids


def test_list_captures_by_date_domain_filter(tmp_brain: Path) -> None:
    capture(text="ml note", domain="ml")
    capture(text="career note", domain="career")
    today_date = _read_meta(
        capture(text="signal").path   # any fresh capture
    )["created_at"][:10]
    rows_ml = list_captures_by_date(today_date, domain="ml")
    assert all(r.domain == "ml" for r in rows_ml)


def test_list_captures_by_date_invalid_date_raises(tmp_brain: Path) -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        list_captures_by_date("2026/04/23")


def test_list_captures_excludes_missing_dir(tmp_brain: Path) -> None:
    """brain/signals or brain/domains may not exist yet — don't crash."""
    today_date = "2026-04-23"
    rows = list_captures_by_date(today_date)
    assert rows == []


def test_add_okr_link_appends_deduped(tmp_brain: Path) -> None:
    r = capture(text="linked memo", domain="ml")
    result = add_okr_link(r.path.stem, ["2026-Q2-mle-role.kr-1"])
    assert result == ["2026-Q2-mle-role.kr-1"]
    # Adding same + a new one: dedup + append
    result2 = add_okr_link(
        r.path.stem,
        ["2026-Q2-mle-role.kr-1", "2026-Q2-mle-role.kr-2"],
    )
    assert result2 == ["2026-Q2-mle-role.kr-1", "2026-Q2-mle-role.kr-2"]


def test_add_okr_link_preserves_existing_field(tmp_brain: Path) -> None:
    r = capture(
        text="already linked",
        domain="ml",
        okrs=["2026-Q2-x.kr-1"],
    )
    result = add_okr_link(r.path.stem, ["2026-Q2-x.kr-2"])
    assert result == ["2026-Q2-x.kr-1", "2026-Q2-x.kr-2"]


def test_add_okr_link_missing_capture_raises(tmp_brain: Path) -> None:
    with pytest.raises(MemoNotFound):
        add_okr_link("2026-99-99-nope", ["x.kr-1"])


# ─── add_task_link ─────────────────────────────────────────────────────

def test_add_task_link_appends_deduped(tmp_brain: Path) -> None:
    r = capture(text="task linked", domain="ml")
    result = add_task_link(r.path.stem, ["notion-task-1"])
    assert result == ["notion-task-1"]
    # idempotent + appends new
    result2 = add_task_link(r.path.stem, ["notion-task-1", "notion-task-2"])
    assert result2 == ["notion-task-1", "notion-task-2"]
    # frontmatter actually persisted
    assert _read_meta(r.path)["tasks"] == ["notion-task-1", "notion-task-2"]


def test_add_task_link_preserves_okrs_field(tmp_brain: Path) -> None:
    r = capture(
        text="dual linked",
        domain="ml",
        okrs=["2026-Q2-x.kr-1"],
    )
    add_task_link(r.path.stem, ["task-page-id"])
    meta = _read_meta(r.path)
    assert meta["okrs"] == ["2026-Q2-x.kr-1"]
    assert meta["tasks"] == ["task-page-id"]


def test_add_task_link_empty_input_no_op(tmp_brain: Path) -> None:
    r = capture(text="will be touched", domain="ml")
    # Empty/whitespace inputs are filtered — locator still runs
    assert add_task_link(r.path.stem, []) == []
    assert add_task_link(r.path.stem, ["", "  "]) == []
    # tasks field was never written
    assert "tasks" not in _read_meta(r.path)


def test_add_task_link_strips_whitespace(tmp_brain: Path) -> None:
    r = capture(text="strip test", domain="ml")
    result = add_task_link(r.path.stem, ["  abc-123  "])
    assert result == ["abc-123"]


def test_add_task_link_missing_capture_raises(tmp_brain: Path) -> None:
    with pytest.raises(MemoNotFound):
        add_task_link("2026-99-99-nope", ["page-id"])


# ─── daily_file_path / upsert_daily_section ────────────────────────────

def test_daily_file_path_splits_ymd(tmp_brain: Path) -> None:
    p = daily_file_path("2026-04-23")
    assert p.is_relative_to(tmp_brain / "daily" / "2026" / "04")
    assert p.name == "23.md"


def test_daily_file_path_rejects_invalid(tmp_brain: Path) -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        daily_file_path("04/23/2026")


def test_upsert_daily_section_creates_file_with_frontmatter(tmp_brain: Path) -> None:
    path = upsert_daily_section("2026-04-23", "Morning Brief", "오늘 우선순위 3")
    assert path.exists()
    post = frontmatter.load(path)
    assert post.metadata["type"] == "daily"
    assert post.metadata["date"] == "2026-04-23"
    assert "## Morning Brief" in post.content
    assert "오늘 우선순위 3" in post.content


def test_upsert_daily_section_appends_new_heading(tmp_brain: Path) -> None:
    upsert_daily_section("2026-04-23", "Morning Brief", "morning body")
    upsert_daily_section("2026-04-23", "Evening Retro", "evening body")
    body = frontmatter.load(daily_file_path("2026-04-23")).content
    assert "## Morning Brief" in body
    assert "## Evening Retro" in body
    assert body.index("Morning Brief") < body.index("Evening Retro")


def test_upsert_daily_section_replaces_existing_body(tmp_brain: Path) -> None:
    upsert_daily_section("2026-04-23", "Morning Brief", "first version")
    upsert_daily_section("2026-04-23", "Morning Brief", "second version")
    body = frontmatter.load(daily_file_path("2026-04-23")).content
    assert "second version" in body
    assert "first version" not in body


def test_upsert_daily_section_preserves_other_sections(tmp_brain: Path) -> None:
    upsert_daily_section("2026-04-23", "Morning Brief", "morning v1")
    upsert_daily_section("2026-04-23", "Evening Retro", "evening v1")
    upsert_daily_section("2026-04-23", "Morning Brief", "morning v2")
    body = frontmatter.load(daily_file_path("2026-04-23")).content
    assert "morning v2" in body
    assert "evening v1" in body   # evening section intact
    assert "morning v1" not in body


def test_read_daily_returns_full_markdown(tmp_brain: Path) -> None:
    upsert_daily_section("2026-04-23", "Morning Brief", "오늘 우선순위 3")
    result = read_daily("2026-04-23")
    assert result["exists"] is True
    assert "## Morning Brief" in result["content"]
    assert "오늘 우선순위 3" in result["content"]
    assert result["content"].startswith("---")  # frontmatter included
    assert result["path"] == str(daily_file_path("2026-04-23"))


def test_read_daily_missing_file_returns_empty(tmp_brain: Path) -> None:
    result = read_daily("2026-04-22")
    assert result["exists"] is False
    assert result["content"] == ""
    assert result["path"] == str(daily_file_path("2026-04-22"))


def test_read_daily_invalid_date_raises(tmp_brain: Path) -> None:
    with pytest.raises(ValueError):
        read_daily("2026/04/23")


# ─── FR-C4.2: watcher entity backlink hook ─────────────────────────────

def test_supplement_fires_entity_backlinks_when_entities_present(tmp_brain: Path) -> None:
    """A watcher-supplemented file with entities frontmatter must auto-link."""
    from mcs.adapters import entity as ent
    from mcs.adapters.memory import _body_hash

    ent.create_draft(kind="people", name="Jane Smith")
    ent.confirm("people/jane-smith")

    (tmp_brain / "signals").mkdir()
    path = tmp_brain / "signals" / "2026-05-01-watcher-drop.md"
    body = "body\n"
    path.write_text(
        "---\n"
        "id: 2026-05-01-watcher-drop\n"
        "type: signal\n"
        "domain: null\n"
        "entities: [people/jane-smith]\n"
        "created_at: '2026-05-01T00:00:00+09:00'\n"
        "source: file-watcher\n"
        f"body_hash: {_body_hash(body)}\n"
        f"---\n\n{body}",
        encoding="utf-8",
    )
    # Frontmatter complete + hash matches → no rewrite, but backlink fires.
    assert supplement_frontmatter(path) is False

    profile = (tmp_brain / "entities/people/jane-smith.md").read_text(encoding="utf-8")
    auto = profile.split("AUTO-GENERATED BELOW. DO NOT EDIT. -->")[1].split("<!-- END")[0]
    lines = [ln for ln in auto.strip().splitlines() if ln.strip()]
    assert any("watcher-drop" in ln for ln in lines)


def test_supplement_silent_for_missing_entity(tmp_brain: Path) -> None:
    """Unknown entity slug → no error, file written normally."""
    from mcs.adapters.memory import _body_hash
    (tmp_brain / "signals").mkdir()
    path = tmp_brain / "signals" / "x.md"
    body = "body\n"
    path.write_text(
        "---\nid: x\ntype: signal\ndomain: null\nentities: [people/no-such]\n"
        "created_at: '2026-05-01T00:00:00+09:00'\nsource: file-watcher\n"
        f"body_hash: {_body_hash(body)}\n---\n\n{body}",
        encoding="utf-8",
    )
    # No EntityNotFound bubble-up
    assert supplement_frontmatter(path) is False


# ─── set_domain (Phase 7.1) ────────────────────────────────────────────

def test_set_domain_overwrites_field(tmp_brain: Path) -> None:
    from mcs.adapters.memory import set_domain
    rec = capture(text="hi", title="t1")  # signal, no domain
    assert _read_meta(rec.path)["domain"] is None

    out = set_domain(rec.id, "career")
    assert out.domain == "career"
    assert out.moved_from is None  # default move=False
    assert _read_meta(rec.path)["domain"] == "career"


def test_set_domain_clears_with_none(tmp_brain: Path) -> None:
    from mcs.adapters.memory import set_domain
    rec = capture(text="hi", domain="career", title="t1")
    out = set_domain(rec.id, None)
    assert out.domain is None
    assert _read_meta(rec.path)["domain"] is None


def test_set_domain_rejects_unknown(tmp_brain: Path) -> None:
    from mcs.adapters.memory import set_domain
    rec = capture(text="hi", title="t1")
    with pytest.raises(ValueError, match="Unknown domain"):
        set_domain(rec.id, "not-a-real-domain")


def test_set_domain_is_idempotent(tmp_brain: Path) -> None:
    """Setting same domain leaves the file untouched (no rewrite)."""
    from mcs.adapters.memory import set_domain
    rec = capture(text="hi", domain="career", title="t1")
    mtime_before = rec.path.stat().st_mtime_ns
    set_domain(rec.id, "career")
    mtime_after = rec.path.stat().st_mtime_ns
    assert mtime_before == mtime_after


# ─── set_domain move=True (Phase 8.1) ──────────────────────────────────

def test_set_domain_moves_signal_to_domains_when_move_true(tmp_brain: Path) -> None:
    from mcs.adapters.memory import set_domain
    rec = capture(text="career memo", title="t1")  # signal
    assert rec.path.is_relative_to(tmp_brain / "signals")

    out = set_domain(rec.id, "career", move=True)
    assert out.domain == "career"
    assert out.moved_from == rec.path
    assert out.path.is_relative_to(tmp_brain / "domains" / "career")
    assert not rec.path.exists()
    assert _read_meta(out.path)["domain"] == "career"


def test_set_domain_no_move_for_cross_domain(tmp_brain: Path) -> None:
    """X→Y is too risky for v0; tag changes, file stays put."""
    from mcs.adapters.memory import set_domain
    rec = capture(text="hi", domain="career", title="t1")
    out = set_domain(rec.id, "ml", move=True)
    assert out.moved_from is None
    assert out.path == rec.path
    assert _read_meta(out.path)["domain"] == "ml"


def test_set_domain_no_move_when_clearing(tmp_brain: Path) -> None:
    from mcs.adapters.memory import set_domain
    rec = capture(text="hi", domain="career", title="t1")
    out = set_domain(rec.id, None, move=True)
    assert out.moved_from is None


def test_set_domain_collision_uses_suffix(tmp_brain: Path) -> None:
    """If the destination filename is taken, the move uses a -2 suffix."""
    from mcs.adapters.memory import set_domain
    (tmp_brain / "domains" / "career").mkdir(parents=True)
    (tmp_brain / "domains" / "career" / "2026-04-22-shared.md").write_text(
        "---\nid: 2026-04-22-shared\ndomain: career\ntype: note\n"
        "entities: []\ncreated_at: '2026-04-22T00:00:00+09:00'\n"
        "source: typed\n---\n\nbody\n",
        encoding="utf-8",
    )
    (tmp_brain / "signals").mkdir(exist_ok=True)
    sig = tmp_brain / "signals" / "2026-04-22-shared.md"
    sig.write_text(
        "---\nid: 2026-04-22-shared\ndomain: null\ntype: signal\n"
        "entities: []\ncreated_at: '2026-04-22T00:00:00+09:00'\n"
        "source: typed\n---\n\nsignal body\n",
        encoding="utf-8",
    )

    # Disambiguate by full path since the stem matches both files.
    out = set_domain("signals/2026-04-22-shared", "career", move=True)
    assert out.path.name == "2026-04-22-shared-2.md"
    assert _read_meta(out.path)["id"] == "2026-04-22-shared-2"


# ─── Phase 8.3: id mismatch triggers rewrite + extractor re-fire ────────

def test_supplement_corrects_id_when_filename_changed(tmp_brain: Path) -> None:
    """Obsidian-rename scenario: id=Untitled but filename differs → rewrite."""
    (tmp_brain / "signals").mkdir()
    path = tmp_brain / "signals" / "2026-05-01-renamed.md"
    path.write_text(
        "---\n"
        "id: Untitled\n"
        "type: signal\n"
        "domain: null\n"
        "entities: []\n"
        "created_at: '2026-05-01T00:00:00+09:00'\n"
        "source: file-watcher\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )

    rewritten = supplement_frontmatter(path)
    assert rewritten is True
    assert _read_meta(path)["id"] == "2026-05-01-renamed"


def test_supplement_no_rewrite_when_id_matches_stem(tmp_brain: Path) -> None:
    from mcs.adapters.memory import _body_hash
    (tmp_brain / "signals").mkdir()
    path = tmp_brain / "signals" / "good.md"
    body = "body\n"
    path.write_text(
        "---\nid: good\ntype: signal\ndomain: null\nentities: []\n"
        "created_at: '2026-05-01T00:00:00+09:00'\nsource: typed\n"
        f"body_hash: {_body_hash(body)}\n---\n\n{body}",
        encoding="utf-8",
    )
    assert supplement_frontmatter(path) is False


# ─── Phase 9: body_hash re-extract trigger ─────────────────────────────

def test_capture_records_body_hash(tmp_brain: Path) -> None:
    rec = capture(text="hello body", title="hash-1")
    meta = _read_meta(rec.path)
    assert "body_hash" in meta
    assert len(meta["body_hash"]) == 64  # sha256 hex


def test_supplement_no_op_when_body_unchanged(tmp_brain: Path) -> None:
    """Re-running supplement on a complete file with matching hash → no-op."""
    rec = capture(text="hello body", title="hash-2")
    assert supplement_frontmatter(rec.path) is False


def test_supplement_rewrites_when_body_changes(tmp_brain: Path) -> None:
    """Edit the body → next supplement detects hash mismatch and rewrites."""
    rec = capture(text="original body", title="hash-3")
    original_hash = _read_meta(rec.path)["body_hash"]

    # Simulate an external edit (Obsidian save with new content).
    post = frontmatter.load(rec.path)
    post.content = "completely different body now\n"
    rec.path.write_text(
        frontmatter.dumps(frontmatter.Post(post.content, **post.metadata)) + "\n",
        encoding="utf-8",
    )

    rewritten = supplement_frontmatter(rec.path)
    assert rewritten is True
    new_hash = _read_meta(rec.path)["body_hash"]
    assert new_hash != original_hash


def test_supplement_ignores_whitespace_only_changes(tmp_brain: Path) -> None:
    """Trailing whitespace shouldn't trigger re-extraction (LLM cost guard)."""
    rec = capture(text="stable body", title="hash-4")

    # Add trailing spaces and a blank line — body content semantically same.
    post = frontmatter.load(rec.path)
    post.content = "stable body   \n   \n"
    rec.path.write_text(
        frontmatter.dumps(frontmatter.Post(post.content, **post.metadata)) + "\n",
        encoding="utf-8",
    )

    assert supplement_frontmatter(rec.path) is False


def test_supplement_backfills_body_hash_on_legacy_file(tmp_brain: Path) -> None:
    """Files written before Phase 9 lack body_hash; supplement adds it once."""
    (tmp_brain / "signals").mkdir()
    path = tmp_brain / "signals" / "legacy.md"
    path.write_text(
        "---\nid: legacy\ntype: signal\ndomain: null\nentities: []\n"
        "created_at: '2026-04-01T00:00:00+09:00'\nsource: typed\n---\n\nold body\n",
        encoding="utf-8",
    )
    # Missing body_hash + complete required → still rewrites (= re-fire).
    assert supplement_frontmatter(path) is True
    assert "body_hash" in _read_meta(path)


def test_set_domain_move_relocates_already_classified_signal(tmp_brain: Path) -> None:
    """User-reported gap: file has domain set but is still in signals/.
    set_domain(same_domain, move=True) should still relocate it."""
    from mcs.adapters.memory import set_domain
    # Simulate the stuck state: signals/ file with domain already set.
    (tmp_brain / "signals").mkdir(exist_ok=True)
    sig = tmp_brain / "signals" / "stuck.md"
    sig.write_text(
        "---\nid: stuck\ntype: signal\ndomain: career\nentities: []\n"
        "created_at: '2026-05-01T00:00:00+09:00'\nsource: file-watcher\n"
        "body_hash: dummy\n---\n\nbody\n",
        encoding="utf-8",
    )

    out = set_domain("stuck", "career", move=True)
    assert out.moved_from == sig
    assert "domains/career" in str(out.path)
    assert not sig.exists()
