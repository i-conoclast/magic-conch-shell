"""Skill-detection corpus (FR-E5 detector input).

Source-agnostic abstraction over "things the user wrote that might
hint at a recurring skill". v0 ships with one source — captures
(`brain/signals/`, `brain/domains/X/`). Future sources (Hermes session
openers via shim, plan-confirmed tasks, etc.) plug in by adding to the
`_CORPUS_SOURCES` registry without touching the detector.

Mirrors the `inbox._SOURCES` pattern so the registry style is consistent
across mcs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import frontmatter

from mcs.config import load_settings


_KST = ZoneInfo("Asia/Seoul")


# ─── data ──────────────────────────────────────────────────────────────

@dataclass
class CorpusItem:
    """One unit of evidence the detector can cluster.

    `id` is globally unique across sources (source-prefixed) so the
    detector can dedupe and reference items unambiguously.
    """

    id: str                # e.g. "capture:signals/2026-05-01-foo"
    text: str              # the body content used for embedding
    source_type: str       # "capture" | "session-opener" | …
    created_at: datetime   # timezone-aware (KST)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "source_type": self.source_type,
            "created_at": self.created_at.isoformat(),
            "payload": self.payload,
        }


# ─── source: captures ──────────────────────────────────────────────────

_CAPTURE_ROOTS = ("signals", "domains")


def _parse_dt(raw: Any) -> datetime | None:
    """Best-effort ISO datetime parse; tz-naive → KST."""
    if raw is None:
        return None
    s = str(raw)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_KST)
    return dt


def _list_captures(*, since: datetime | None = None) -> list[CorpusItem]:
    """Walk brain/signals + brain/domains/* and yield each .md as a CorpusItem.

    Files outside the date window are skipped early (cheap stat() vs full
    read for older paths). Files whose body is shorter than ~5 chars are
    skipped — they're not useful for clustering.
    """
    settings = load_settings()
    brain = settings.brain_dir.resolve()
    out: list[CorpusItem] = []

    for sub in _CAPTURE_ROOTS:
        root = brain / sub
        if not root.exists():
            continue
        for record in root.rglob("*.md"):
            try:
                post = frontmatter.load(record)
            except Exception:
                continue

            meta = post.metadata or {}
            created_at = _parse_dt(meta.get("created_at"))
            if created_at is None:
                # fall back to mtime so legacy files aren't dropped
                created_at = datetime.fromtimestamp(record.stat().st_mtime, tz=_KST)

            if since is not None and created_at < since:
                continue

            body = (post.content or "").strip()
            if len(body) < 5:
                continue

            try:
                rel = record.relative_to(brain).with_suffix("").as_posix()
            except ValueError:
                continue

            out.append(
                CorpusItem(
                    id=f"capture:{rel}",
                    text=body,
                    source_type="capture",
                    created_at=created_at,
                    payload={
                        "rel_path": rel,
                        "abs_path": str(record.resolve()),
                        "type": meta.get("type"),
                        "domain": meta.get("domain"),
                        "entities": list(meta.get("entities") or []),
                    },
                )
            )
    return out


# ─── registry ──────────────────────────────────────────────────────────
#
# To add a new source (e.g. Hermes session openers via shim in a future
# phase), bind a list_fn here. The detector iterates whatever sources
# are registered and asked for, never the source identity directly.

ListFn = Callable[..., list[CorpusItem]]

_CORPUS_SOURCES: dict[str, ListFn] = {
    "capture": _list_captures,
}


def register_source(name: str, list_fn: ListFn) -> None:
    """Late-binding hook so plugins/test code can extend the corpus.

    Mostly there for symmetry with `inbox` — Phase 12 only ships
    `capture`.
    """
    _CORPUS_SOURCES[name] = list_fn


def known_sources() -> list[str]:
    return sorted(_CORPUS_SOURCES.keys())


# ─── public API ────────────────────────────────────────────────────────

def list_corpus(
    *,
    since: datetime | None = None,
    source_types: list[str] | None = None,
) -> list[CorpusItem]:
    """Return the unified corpus, oldest first.

    Stable order across sources: by `created_at` ascending, then by `id`.
    """
    items: list[CorpusItem] = []
    types = source_types or known_sources()
    for t in types:
        fn = _CORPUS_SOURCES.get(t)
        if fn is None:
            continue
        items.extend(fn(since=since))
    items.sort(key=lambda it: (it.created_at, it.id))
    return items


__all__ = [
    "CorpusItem",
    "known_sources",
    "list_corpus",
    "register_source",
]
