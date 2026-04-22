"""Search adapter — memsearch wrapper with filters.

memsearch handles incremental indexing via chunk_hash natively.
- index(force=False): only re-embeds changed files
- index_file(path):    single-file upsert (used after capture)
- search(source_prefix=...): path-prefix filter (domains, type routing)

Entity filter is post-applied by reading frontmatter.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import frontmatter
from memsearch import MemSearch

from mcs.adapters.memory import DOMAINS
from mcs.config import load_settings


# Matches a leading YAML frontmatter block (opening --- to closing ---)
_FRONTMATTER_BLOCK = re.compile(r"^---\s*\n.*?\n---\s*\n?", re.DOTALL)


def _strip_frontmatter(text: str) -> str:
    """Remove the leading YAML frontmatter block from a raw chunk."""
    return _FRONTMATTER_BLOCK.sub("", text, count=1).strip()


@dataclass
class SearchHit:
    """One search result row."""

    score: float
    path: Path                 # absolute path
    rel_path: str              # display path, relative to repo root
    snippet: str               # content excerpt
    domain: str | None
    type: str                  # signal | note | ...
    entities: list[str]
    chunk_hash: str | None
    start_line: int | None
    end_line: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "path": str(self.path),
            "rel_path": self.rel_path,
            "snippet": self.snippet,
            "domain": self.domain,
            "type": self.type,
            "entities": self.entities,
            "chunk_hash": self.chunk_hash,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


# ─── Singleton engine ───────────────────────────────────────────────────

_engine: MemSearch | None = None
_indexed_once: bool = False


def _build_engine() -> MemSearch:
    """Construct MemSearch from settings."""
    settings = load_settings()
    brain = settings.brain_dir.resolve()
    cache = settings.cache_dir.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    milvus_db = cache / "memsearch.db"

    # embedding_base_url: memsearch expects base without /v1 (uses /api/embeddings)
    base_url = settings.ollama_base_url.rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]

    return MemSearch(
        paths=[str(brain)],
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
        embedding_base_url=base_url,
        milvus_uri=str(milvus_db),
    )


def get_engine() -> MemSearch:
    """Return process-wide MemSearch instance."""
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


async def ensure_indexed() -> int:
    """Incremental index on first call per process.

    Returns the number of chunks re-embedded this invocation.
    memsearch skips unchanged files via chunk_hash comparison.
    """
    global _indexed_once
    ms = get_engine()
    indexed = await ms.index(force=False)
    _indexed_once = True
    return indexed


async def sync_file(path: Path | str) -> int:
    """Upsert a single file into the index.

    Call this after a capture to make the new memo searchable
    without waiting for the next ensure_indexed() scan.
    """
    ms = get_engine()
    return await ms.index_file(str(path))


async def rebuild_all() -> int:
    """Force full re-embedding of the whole brain/.

    Use for `mcs reindex`, schema upgrades, or corruption recovery.
    """
    ms = get_engine()
    return await ms.index(force=True)


# ─── Search ─────────────────────────────────────────────────────────────

def _prefix_for(
    brain: Path,
    domain: str | None,
    type_: str | None,
) -> str | None:
    """Resolve the filesystem prefix memsearch should restrict to."""
    if domain:
        return str(brain / "domains" / domain)
    if type_ == "signal":
        return str(brain / "signals")
    if type_ == "note":
        return str(brain / "domains")
    if type_ == "daily":
        return str(brain / "daily")
    if type_ == "entity":
        return str(brain / "entities")
    return None


def _load_meta(path: Path) -> tuple[str, str | None, list[str]]:
    """Return (type, domain, entities) from a brain file's frontmatter.

    Falls back to ('', None, []) when the file is missing or malformed.
    """
    try:
        post = frontmatter.load(path)
    except Exception:
        return "", None, []
    meta = post.metadata or {}
    return (
        str(meta.get("type") or ""),
        (meta.get("domain") or None),
        list(meta.get("entities") or []),
    )


async def search(
    query: str,
    *,
    domain: str | None = None,
    type: str | None = None,
    entity: str | None = None,
    limit: int = 10,
    auto_index: bool = True,
) -> list[SearchHit]:
    """Hybrid search over brain/ with optional filters.

    Args:
        query:      Free-form query (Korean/English ok).
        domain:     Restrict to brain/domains/{domain}/. Implies type=note.
        type:       'signal' | 'note' | 'daily' | 'entity' (path routing).
        entity:     Post-filter: require this entity in frontmatter.
        limit:      Max results to return.
        auto_index: Run ensure_indexed() first (default True).

    Returns:
        List of SearchHit, highest score first.
    """
    if domain is not None and domain not in DOMAINS:
        raise ValueError(
            f"Unknown domain {domain!r}. Valid: {sorted(DOMAINS)}"
        )

    settings = load_settings()
    brain = settings.brain_dir.resolve()
    repo_root = settings.repo_root.resolve()

    if auto_index:
        await ensure_indexed()

    ms = get_engine()
    prefix = _prefix_for(brain, domain, type)
    # Overfetch when post-filtering by entity, since memsearch
    # doesn't know frontmatter — we drop non-matching rows client-side.
    fetch_k = limit * 4 if entity else limit

    raw = await ms.search(query, top_k=fetch_k, source_prefix=prefix)

    hits: list[SearchHit] = []
    for r in raw:
        source = r.get("source") or r.get("path") or ""
        if not source:
            continue
        path = Path(source).resolve()
        row_type, row_domain, row_entities = _load_meta(path)

        if entity and entity not in row_entities:
            continue

        try:
            rel = str(path.relative_to(repo_root))
        except ValueError:
            rel = str(path)

        hits.append(
            SearchHit(
                score=float(r.get("score") or r.get("distance") or 0.0),
                path=path,
                rel_path=rel,
                snippet=_strip_frontmatter(str(r.get("content") or r.get("text") or "")),
                domain=row_domain,
                type=row_type,
                entities=row_entities,
                chunk_hash=r.get("chunk_hash"),
                start_line=r.get("start_line"),
                end_line=r.get("end_line"),
            )
        )
        if len(hits) >= limit:
            break

    return hits
