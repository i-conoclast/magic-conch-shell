"""ANN-based skill candidate detector (FR-E5 v0).

Reads a `skill_corpus` snapshot, asks memsearch for each item's
top-K nearest neighbours, builds similarity edges above a threshold,
runs a union-find over the resulting graph, and returns candidate
clusters that pass size + time-spread + average-score gates.

Intentionally simple — no UMAP/HDBSCAN, no LLM. Phase 12.3 layers
LLM labelling and exclusion checks on top of these candidates.
The detector is corpus-source agnostic: when a future phase plugs
session-opener shims into `skill_corpus`, this module needs no changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

from mcs.adapters import search as search_mod
from mcs.adapters.skill_corpus import CorpusItem
from mcs.config import load_settings


# ─── data ──────────────────────────────────────────────────────────────

@dataclass
class SimEdge:
    a_id: str
    b_id: str
    score: float


@dataclass
class SkillCandidate:
    """One detected cluster of similar items.

    No suggested slug yet — Phase 12.3 (LLM labelling) fills that in.
    """

    seed_id: str
    member_ids: list[str]
    sample_texts: list[str]
    avg_score: float
    earliest: datetime
    latest: datetime
    edge_count: int
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def time_spread_days(self) -> float:
        return (self.latest - self.earliest).total_seconds() / 86400.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed_id": self.seed_id,
            "member_ids": self.member_ids,
            "sample_texts": self.sample_texts,
            "avg_score": self.avg_score,
            "earliest": self.earliest.isoformat(),
            "latest": self.latest.isoformat(),
            "edge_count": self.edge_count,
            "time_spread_days": round(self.time_spread_days, 2),
            "payload": self.payload,
        }


# ─── ID resolution ─────────────────────────────────────────────────────
#
# A SearchHit comes back with a filesystem path; we need the matching
# CorpusItem id (e.g. "capture:domains/career/2026-05-01-foo") so the
# edges can reference items, not paths. Today only `capture` is wired,
# but the helper is structured so other source types can opt in by
# providing their own SearchHit-to-id translator.

def _hit_to_capture_id(hit: search_mod.SearchHit) -> str | None:
    settings = load_settings()
    brain = settings.brain_dir.resolve()
    try:
        rel = hit.path.relative_to(brain).with_suffix("").as_posix()
    except ValueError:
        return None
    if not (rel.startswith("signals/") or rel.startswith("domains/")):
        return None
    return f"capture:{rel}"


def _hit_to_id(hit: search_mod.SearchHit) -> str | None:
    return _hit_to_capture_id(hit)


# ─── union-find ────────────────────────────────────────────────────────

class _DSU:
    """Tiny disjoint-set / union-find over arbitrary string ids."""

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb

    def groups(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for x in list(self.parent.keys()):
            r = self.find(x)
            out.setdefault(r, []).append(x)
        return out


# ─── main entry point ──────────────────────────────────────────────────

# Thin alias so tests can swap out memsearch with a fake.
SearchFn = Callable[[str], Awaitable[list[search_mod.SearchHit]]]


async def _default_search(query: str, *, top_k: int) -> list[search_mod.SearchHit]:
    return await search_mod.search(query, limit=top_k, auto_index=False)


async def find_candidates(
    corpus: list[CorpusItem],
    *,
    similarity_threshold: float = 0.020,
    top_k: int = 8,
    min_cluster_size: int = 4,
    min_time_spread_days: float = 2.0,
    min_avg_score: float = 0.020,
    search_fn: SearchFn | None = None,
) -> list[SkillCandidate]:
    """Cluster `corpus` items by ANN-derived similarity.

    Each item queries memsearch for its `top_k` nearest neighbours;
    edges above `similarity_threshold` are added to a union-find.
    Components that meet `min_cluster_size`, `min_time_spread_days`,
    and `min_avg_score` are returned as `SkillCandidate`s.

    NOTE on score range: memsearch returns RRF (Reciprocal Rank Fusion)
    scores, not cosine similarity. RRF with k=60 caps top-1 at ~0.033
    (1/61 from dense + 1/61 from BM25), and unrelated chunks fall to
    ~0.016. Defaults are calibrated for this range; do not pass
    cosine-style thresholds (0.5–0.9) here — the detector will return
    nothing.

    `search_fn` is injectable so tests can drive the algorithm with
    a deterministic neighbour map. When omitted the live memsearch
    engine handles the queries.
    """
    if not corpus:
        return []

    by_id = {it.id: it for it in corpus}

    # 1) Build similarity edges via ANN.
    edges: list[SimEdge] = []
    seen_pairs: set[tuple[str, str]] = set()
    for item in corpus:
        if search_fn is not None:
            hits = await search_fn(item.text)
        else:
            hits = await _default_search(item.text, top_k=top_k)
        for h in hits:
            other_id = _hit_to_id(h)
            if other_id is None or other_id == item.id or other_id not in by_id:
                continue
            if h.score < similarity_threshold:
                continue
            pair = tuple(sorted((item.id, other_id)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            edges.append(SimEdge(pair[0], pair[1], h.score))

    if not edges:
        return []

    # 2) Union-find — every edge merges two ids into the same component.
    dsu = _DSU()
    for it in corpus:
        dsu.find(it.id)
    for e in edges:
        dsu.union(e.a_id, e.b_id)

    # 3) Score + filter clusters.
    components = dsu.groups()
    candidates: list[SkillCandidate] = []
    edges_by_root: dict[str, list[SimEdge]] = {}
    for e in edges:
        root = dsu.find(e.a_id)
        edges_by_root.setdefault(root, []).append(e)

    for root, ids in components.items():
        if len(ids) < min_cluster_size:
            continue

        members = [by_id[i] for i in ids if i in by_id]
        if len(members) < min_cluster_size:
            continue

        timestamps = [m.created_at for m in members]
        earliest = min(timestamps)
        latest = max(timestamps)
        spread_days = (latest - earliest).total_seconds() / 86400.0
        if spread_days < min_time_spread_days:
            continue

        cluster_edges = edges_by_root.get(root, [])
        if not cluster_edges:
            continue
        avg_score = sum(e.score for e in cluster_edges) / len(cluster_edges)
        if avg_score < min_avg_score:
            continue

        # Seed = oldest member; gives the LLM a stable anchor for naming.
        members_sorted = sorted(members, key=lambda m: m.created_at)
        seed = members_sorted[0]
        sample_texts = [m.text[:200] for m in members_sorted[:5]]

        candidates.append(
            SkillCandidate(
                seed_id=seed.id,
                member_ids=[m.id for m in members_sorted],
                sample_texts=sample_texts,
                avg_score=avg_score,
                earliest=earliest,
                latest=latest,
                edge_count=len(cluster_edges),
                payload={
                    "source_types": sorted({m.source_type for m in members}),
                    "domains": sorted({
                        d for m in members
                        if (d := m.payload.get("domain")) is not None
                    }),
                },
            )
        )

    candidates.sort(key=lambda c: (c.avg_score, len(c.member_ids)), reverse=True)
    return candidates


__all__ = [
    "SearchFn",
    "SimEdge",
    "SkillCandidate",
    "find_candidates",
]
