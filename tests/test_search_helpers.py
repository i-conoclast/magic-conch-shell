"""Unit tests for pure helpers in mcs.adapters.search.

No Ollama / no memsearch engine is spun up here — these cover
the file-system and frontmatter logic the search command relies on.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mcs.adapters.search import (
    _load_meta,
    _prefix_for,
    _strip_frontmatter,
)


# ─── _strip_frontmatter ─────────────────────────────────────────────────

def test_strip_frontmatter_removes_leading_yaml() -> None:
    raw = (
        "---\n"
        "id: 2026-04-22-foo\n"
        "type: note\n"
        "---\n"
        "\n"
        "body text here\n"
    )
    assert _strip_frontmatter(raw) == "body text here"


def test_strip_frontmatter_leaves_plain_text_untouched() -> None:
    assert _strip_frontmatter("just a body") == "just a body"


def test_strip_frontmatter_only_removes_leading_block() -> None:
    """`---` inside the body (e.g. horizontal rule) is not a frontmatter fence."""
    raw = (
        "---\n"
        "id: x\n"
        "---\n"
        "intro\n"
        "---\n"
        "after-rule\n"
    )
    out = _strip_frontmatter(raw)
    assert out.startswith("intro")
    assert "after-rule" in out


# ─── _prefix_for ────────────────────────────────────────────────────────
#
# Domain no longer drives the path prefix — it's enforced via frontmatter
# so Objectives / KRs / signals tagged with the domain all surface. The
# prefix is kept only as a speed hint for `type` values that map cleanly
# to a single folder.


def test_prefix_for_domain_alone_returns_none(tmp_path: Path) -> None:
    """Domain filtering happens in frontmatter, not via path prefix."""
    assert _prefix_for(tmp_path, domain="career", type_=None) is None


def test_prefix_for_signal_type_points_at_signals(tmp_path: Path) -> None:
    assert _prefix_for(tmp_path, domain=None, type_="signal") == str(
        tmp_path / "signals"
    )


def test_prefix_for_note_type_returns_none(tmp_path: Path) -> None:
    """note spans brain/domains/* so there's no single tight prefix."""
    assert _prefix_for(tmp_path, domain=None, type_="note") is None


def test_prefix_for_objective_points_at_objectives(tmp_path: Path) -> None:
    assert _prefix_for(tmp_path, domain=None, type_="objective") == str(
        tmp_path / "objectives"
    )


def test_prefix_for_kr_points_at_objectives(tmp_path: Path) -> None:
    assert _prefix_for(tmp_path, domain=None, type_="kr") == str(
        tmp_path / "objectives"
    )


def test_prefix_for_no_filters_returns_none(tmp_path: Path) -> None:
    assert _prefix_for(tmp_path, domain=None, type_=None) is None


def test_prefix_for_type_wins_domain_ignored(tmp_path: Path) -> None:
    """Domain is always ignored in the prefix — type alone decides."""
    prefix = _prefix_for(tmp_path, domain="ml", type_="signal")
    assert prefix == str(tmp_path / "signals")


# ─── _load_meta ─────────────────────────────────────────────────────────

def test_load_meta_returns_type_domain_entities(tmp_path: Path) -> None:
    f = tmp_path / "x.md"
    f.write_text(
        "---\n"
        "id: x\n"
        "type: note\n"
        "domain: career\n"
        "entities:\n"
        "  - people/jane\n"
        "  - companies/anthropic\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )
    type_, domain, entities = _load_meta(f)
    assert type_ == "note"
    assert domain == "career"
    assert entities == ["people/jane", "companies/anthropic"]


def test_load_meta_handles_null_domain(tmp_path: Path) -> None:
    f = tmp_path / "signal.md"
    f.write_text(
        "---\ntype: signal\ndomain: null\nentities: []\n---\nbody\n",
        encoding="utf-8",
    )
    type_, domain, entities = _load_meta(f)
    assert type_ == "signal"
    assert domain is None
    assert entities == []


def test_load_meta_returns_empty_on_missing_file(tmp_path: Path) -> None:
    type_, domain, entities = _load_meta(tmp_path / "nope.md")
    assert (type_, domain, entities) == ("", None, [])


def test_load_meta_returns_empty_on_malformed_file(tmp_path: Path) -> None:
    f = tmp_path / "broken.md"
    f.write_text("not even yaml\n:::\n", encoding="utf-8")
    type_, domain, entities = _load_meta(f)
    # Defensive contract: graceful fallback, no exception.
    assert isinstance(type_, str)
    assert entities == [] or isinstance(entities, list)
