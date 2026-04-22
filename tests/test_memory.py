"""Unit tests for mcs.adapters.memory.capture()."""
from __future__ import annotations

from pathlib import Path

import frontmatter
import pytest

from mcs.adapters.memory import capture


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
