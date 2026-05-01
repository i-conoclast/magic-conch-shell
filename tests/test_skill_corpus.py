"""Unit tests for mcs.adapters.skill_corpus (FR-E5 detector input)."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from mcs.adapters import skill_corpus as corpus_mod
from mcs.adapters.memory import capture


KST = ZoneInfo("Asia/Seoul")


# ─── capture source ────────────────────────────────────────────────────

def test_list_corpus_includes_signals_and_domains(tmp_brain: Path) -> None:
    a = capture(text="hello world body", title="alpha")           # signal
    b = capture(text="career memo body", domain="career", title="beta")

    items = corpus_mod.list_corpus()
    by_id = {it.id: it for it in items}

    assert f"capture:signals/{a.path.stem}" in by_id
    assert f"capture:domains/career/{b.path.stem}" in by_id
    assert all(it.source_type == "capture" for it in items)


def test_list_corpus_skips_short_bodies(tmp_brain: Path) -> None:
    capture(text="x", title="too-short")          # body == "x" → skipped
    capture(text="meaningful body here", title="ok")

    items = corpus_mod.list_corpus()
    bodies = {it.text for it in items}
    assert "x" not in bodies
    assert "meaningful body here" in bodies


def test_list_corpus_payload_carries_meta(tmp_brain: Path) -> None:
    rec = capture(
        text="career memo body",
        domain="career",
        entities=["people/jane-smith"],
        title="payload-test",
    )
    [item] = corpus_mod.list_corpus()
    assert item.payload["domain"] == "career"
    assert item.payload["entities"] == ["people/jane-smith"]
    assert item.payload["abs_path"] == str(rec.path.resolve())


def test_list_corpus_orders_by_created_at(tmp_brain: Path) -> None:
    older = capture(text="older body", title="older")
    newer = capture(text="newer body", title="newer")

    # Force distinct created_at so the sort is observable.
    import frontmatter
    older_meta = frontmatter.load(older.path)
    older_meta["created_at"] = "2026-04-22T09:00:00+09:00"
    older.path.write_text(
        frontmatter.dumps(frontmatter.Post(older_meta.content, **older_meta.metadata)) + "\n",
        encoding="utf-8",
    )

    items = corpus_mod.list_corpus()
    assert items[0].id.endswith("older")
    assert items[-1].id.endswith("newer")


# ─── since filter ──────────────────────────────────────────────────────

def test_list_corpus_respects_since_filter(tmp_brain: Path) -> None:
    rec = capture(text="old enough body", title="old")
    import frontmatter
    post = frontmatter.load(rec.path)
    post["created_at"] = "2026-01-01T00:00:00+09:00"
    rec.path.write_text(
        frontmatter.dumps(frontmatter.Post(post.content, **post.metadata)) + "\n",
        encoding="utf-8",
    )

    cutoff = datetime(2026, 4, 1, tzinfo=KST)
    assert corpus_mod.list_corpus(since=cutoff) == []


# ─── registry ──────────────────────────────────────────────────────────

def test_register_source_extends_corpus(tmp_brain: Path) -> None:
    fake_called = {"n": 0}

    def fake_source(*, since: datetime | None = None):
        fake_called["n"] += 1
        return [
            corpus_mod.CorpusItem(
                id="fake:abc",
                text="fake item body",
                source_type="fake",
                created_at=datetime(2026, 5, 1, tzinfo=KST),
                payload={"src": "fake"},
            )
        ]

    corpus_mod.register_source("fake", fake_source)
    try:
        items = corpus_mod.list_corpus(source_types=["fake"])
        assert [i.id for i in items] == ["fake:abc"]
        assert fake_called["n"] == 1

        # Default scope still includes capture + fake
        all_types = set(corpus_mod.known_sources())
        assert {"capture", "fake"} <= all_types
    finally:
        # Clean the registry so other tests aren't polluted.
        corpus_mod._CORPUS_SOURCES.pop("fake", None)


def test_list_corpus_filter_by_source_types(tmp_brain: Path) -> None:
    capture(text="a capture body", title="a")
    items = corpus_mod.list_corpus(source_types=["capture"])
    assert all(it.source_type == "capture" for it in items)
    # Unknown source name yields nothing — no crash.
    assert corpus_mod.list_corpus(source_types=["nonexistent"]) == []
