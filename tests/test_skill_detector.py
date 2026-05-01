"""Unit tests for mcs.adapters.skill_detector (FR-E5 v0)."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from mcs.adapters import skill_detector as sd
from mcs.adapters import search as search_mod
from mcs.adapters.skill_corpus import CorpusItem


KST = ZoneInfo("Asia/Seoul")


# ─── helpers ───────────────────────────────────────────────────────────

def _ci(rel: str, *, text: str = "body", days_ago: int = 0) -> CorpusItem:
    """Build a capture-style CorpusItem for tests."""
    when = datetime(2026, 5, 1, 12, 0, tzinfo=KST) - timedelta(days=days_ago)
    return CorpusItem(
        id=f"capture:{rel}",
        text=text,
        source_type="capture",
        created_at=when,
        payload={
            "rel_path": rel,
            "abs_path": f"/tmp/brain/{rel}.md",
            "domain": "career" if "career" in rel else None,
            "type": "signal" if rel.startswith("signals/") else "note",
            "entities": [],
        },
    )


def _hit(rel: str, score: float, brain_root: Path) -> search_mod.SearchHit:
    """Build a SearchHit whose path resolves to a brain-relative `rel`."""
    return search_mod.SearchHit(
        score=score,
        path=(brain_root / f"{rel}.md").resolve(),
        rel_path=f"brain/{rel}.md",
        snippet="",
        domain=None,
        type="signal",
        entities=[],
        chunk_hash=None,
        start_line=None,
        end_line=None,
    )


def _make_search_fn(
    neighbours: dict[str, list[tuple[str, float]]],
    brain_root: Path,
):
    """Return a search_fn that maps query text → predetermined hits.

    Keys of `neighbours` are CorpusItem.text, values are (rel, score)
    pairs that get turned into SearchHit objects rooted at `brain_root`
    (the live brain dir, so _hit_to_id resolves correctly).
    """

    async def _fn(query: str) -> list[search_mod.SearchHit]:
        rels = neighbours.get(query, [])
        return [_hit(rel, score, brain_root) for rel, score in rels]

    return _fn


# ─── empty / trivial cases ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_corpus_returns_empty(tmp_brain: Path) -> None:
    out = await sd.find_candidates([])
    assert out == []


@pytest.mark.asyncio
async def test_no_edges_returns_empty(tmp_brain: Path) -> None:
    corpus = [
        _ci("signals/2026-05-01-a", text="alpha"),
        _ci("signals/2026-05-01-b", text="beta"),
    ]
    fn = _make_search_fn({"alpha": [], "beta": []}, tmp_brain)
    out = await sd.find_candidates(corpus, search_fn=fn)
    assert out == []


# ─── happy path: 4-node cluster with spread ────────────────────────────

@pytest.mark.asyncio
async def test_cluster_above_thresholds_surfaces(tmp_brain: Path) -> None:
    # Four items spread across 4 days; each "sees" the other three at 0.85.
    rels = [
        "signals/2026-04-28-a",
        "signals/2026-04-29-b",
        "signals/2026-04-30-c",
        "signals/2026-05-01-d",
    ]
    texts = ["t-a", "t-b", "t-c", "t-d"]
    corpus = [
        _ci(rel, text=txt, days_ago=4 - i)
        for i, (rel, txt) in enumerate(zip(rels, texts))
    ]

    neighbours = {
        txt: [(other, 0.85) for other in rels if other != f"signals/2026-04-{28+i:02d}-{txt[-1]}"]
        for i, txt in enumerate(texts)
    }
    # Easier: every item sees every other rel at 0.85.
    neighbours = {
        txt: [(rel, 0.85) for rel in rels if rel != f"signals/2026-04-{28+i:02d}-{txt[-1]}"]
        for i, txt in enumerate(texts)
    }

    fn = _make_search_fn(neighbours, tmp_brain)
    candidates = await sd.find_candidates(
        corpus,
        search_fn=fn,
        min_cluster_size=4,
        min_time_spread_days=2.0,
        min_avg_score=0.7,
        similarity_threshold=0.6,
    )
    assert len(candidates) == 1
    c = candidates[0]
    assert sorted(c.member_ids) == sorted(it.id for it in corpus)
    assert c.avg_score == pytest.approx(0.85)
    assert c.time_spread_days >= 2.0
    assert c.payload["source_types"] == ["capture"]


# ─── filtered out: cluster too small ───────────────────────────────────

@pytest.mark.asyncio
async def test_small_cluster_filtered_out(tmp_brain: Path) -> None:
    rels = ["signals/a", "signals/b", "signals/c"]  # 3 < 4
    corpus = [_ci(rel, text=rel.split("/")[-1], days_ago=i) for i, rel in enumerate(rels)]
    neighbours = {
        it.text: [(other, 0.9) for other in rels if other != f"signals/{it.text}"]
        for it in corpus
    }
    fn = _make_search_fn(neighbours, tmp_brain)
    out = await sd.find_candidates(corpus, search_fn=fn, min_cluster_size=4)
    assert out == []


# ─── filtered out: time spread too tight ───────────────────────────────

@pytest.mark.asyncio
async def test_same_day_cluster_filtered_out(tmp_brain: Path) -> None:
    """All four items on the same day → time spread = 0, must be dropped."""
    rels = [f"signals/x-{i}" for i in range(4)]
    corpus = [_ci(rel, text=f"x{i}", days_ago=0) for i, rel in enumerate(rels)]
    neighbours = {
        f"x{i}": [(other, 0.95) for other in rels if other != rels[i]]
        for i in range(4)
    }
    fn = _make_search_fn(neighbours, tmp_brain)
    out = await sd.find_candidates(
        corpus, search_fn=fn, min_time_spread_days=2.0, min_cluster_size=4
    )
    assert out == []


# ─── filtered out: average score below threshold ───────────────────────

@pytest.mark.asyncio
async def test_low_score_cluster_filtered_out(tmp_brain: Path) -> None:
    rels = [f"signals/y-{i}" for i in range(4)]
    corpus = [_ci(rel, text=f"y{i}", days_ago=i) for i, rel in enumerate(rels)]
    neighbours = {
        f"y{i}": [(other, 0.55) for other in rels if other != rels[i]]
        for i in range(4)
    }
    fn = _make_search_fn(neighbours, tmp_brain)
    out = await sd.find_candidates(
        corpus, search_fn=fn, min_avg_score=0.7, similarity_threshold=0.5
    )
    assert out == []


# ─── threshold edge: similarity below cutoff drops the edge ───────────

@pytest.mark.asyncio
async def test_similarity_threshold_excludes_weak_edges(tmp_brain: Path) -> None:
    rels = [f"signals/z-{i}" for i in range(4)]
    corpus = [_ci(rel, text=f"z{i}", days_ago=i) for i, rel in enumerate(rels)]
    # Only z0↔z1 strong, the rest weak — only 2 ids end up in the
    # connected component that has edges, which is below min_cluster_size=4.
    neighbours = {
        "z0": [("signals/z-1", 0.9)],
        "z1": [("signals/z-0", 0.9)],
        "z2": [("signals/z-3", 0.4)],   # below threshold
        "z3": [("signals/z-2", 0.4)],
    }
    fn = _make_search_fn(neighbours, tmp_brain)
    out = await sd.find_candidates(
        corpus,
        search_fn=fn,
        similarity_threshold=0.6,
        min_cluster_size=4,
    )
    assert out == []


# ─── multiple clusters ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_multiple_clusters_returned_sorted(tmp_brain: Path) -> None:
    """Two disjoint clusters of 4 each with different avg scores.

    Higher-score cluster should sort first.
    """
    a_rels = [f"signals/a-{i}" for i in range(4)]
    b_rels = [f"signals/b-{i}" for i in range(4)]
    corpus = (
        [_ci(rel, text=f"a{i}", days_ago=i) for i, rel in enumerate(a_rels)]
        + [_ci(rel, text=f"b{i}", days_ago=i) for i, rel in enumerate(b_rels)]
    )
    neighbours = {
        f"a{i}": [(other, 0.95) for other in a_rels if other != a_rels[i]]
        for i in range(4)
    }
    neighbours.update({
        f"b{i}": [(other, 0.7) for other in b_rels if other != b_rels[i]]
        for i in range(4)
    })

    fn = _make_search_fn(neighbours, tmp_brain)
    out = await sd.find_candidates(
        corpus, search_fn=fn, min_avg_score=0.65, similarity_threshold=0.6
    )
    assert len(out) == 2
    # Highest avg_score sorts first.
    assert out[0].avg_score > out[1].avg_score
    assert any("a-0" in mid for mid in out[0].member_ids)
    assert any("b-0" in mid for mid in out[1].member_ids)
