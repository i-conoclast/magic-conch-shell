"""Unit tests for mcs.adapters.memory.capture() and supplement_frontmatter()."""
from __future__ import annotations

from pathlib import Path

import frontmatter
import pytest

from mcs.adapters.memory import (
    MemoAmbiguous,
    MemoNotFound,
    capture,
    load_memo,
    resolve_memo,
    supplement_frontmatter,
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
    path.write_text("---\nid: x\ntype: signal\ndomain: null\nentities: []\ncreated_at: '2026-04-22T00:00:00+09:00'\nsource: typed\n---\n\nbody\n", encoding="utf-8")

    # All required fields present → no rewrite
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
