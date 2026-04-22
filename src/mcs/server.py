"""magic-conch-shell MCP server — single process that owns brain/ state.

Exposes tools over FastMCP HTTP transport so CLI commands, Hermes Agent,
and the background watcher all share one MemSearch engine instance.
This is the architectural fix for the Milvus Lite single-process lock:
only this process opens `.brain/memsearch.db`.

Tools:
  memory.capture — write one-line memo + incremental index
  memory.search  — hybrid search with domain/type/entity filters
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from mcs.adapters.memory import DOMAINS, capture as core_capture
from mcs.adapters.search import search as core_search, sync_file
from mcs.config import load_settings


# Lifespan state — watcher handle so we can stop it cleanly on shutdown.
_watcher_observer: Any = None


@asynccontextmanager
async def _lifespan(_server: FastMCP):
    """Bind the watcher to the running server loop on startup, stop on shutdown."""
    global _watcher_observer
    # Lazy imports avoid a circular dependency at module-load time.
    from mcs.adapters.watcher import bind_main_loop, start_watcher

    bind_main_loop(asyncio.get_running_loop())

    if _watcher_observer is None and _watch_enabled:
        _watcher_observer, _ = start_watcher()
        settings = load_settings()
        print(
            f"[watcher] active on {settings.brain_dir}/signals + /domains",
            flush=True,
        )

    try:
        yield
    finally:
        if _watcher_observer is not None:
            _watcher_observer.stop()
            _watcher_observer.join(timeout=5.0)
            _watcher_observer = None


# Toggle flipped by run_server() before mcp.run() is called.
_watch_enabled: bool = True


mcp = FastMCP(name="mcs", version="0.1.0", lifespan=_lifespan)


@mcp.tool(
    name="memory.capture",
    description="Capture a one-line memo to brain/ and incrementally index it.",
)
async def memory_capture(
    text: str,
    domain: str | None = None,
    entities: list[str] | None = None,
    source: str = "typed",
    title: str | None = None,
    index: bool = True,
) -> dict[str, Any]:
    """Write a memo. Returns {path, id, type, domain, indexed}."""
    result = core_capture(
        text=text,
        domain=domain,
        entities=entities or [],
        source=source,
        title=title,
    )
    indexed = False
    if index:
        try:
            await sync_file(result.path)
            indexed = True
        except Exception:
            # capture succeeded on disk — indexing is best-effort.
            indexed = False

    settings = load_settings()
    try:
        rel = str(result.path.resolve().relative_to(settings.repo_root.resolve()))
    except ValueError:
        rel = str(result.path)

    return {
        "path": str(result.path),
        "rel_path": rel,
        "id": result.id,
        "type": result.type,
        "domain": result.domain,
        "indexed": indexed,
    }


@mcp.tool(
    name="memory.search",
    description=(
        "Hybrid vector + keyword search over brain/. Filters: "
        f"domain={sorted(DOMAINS)}, type=signal|note|daily|entity, entity=slug."
    ),
)
async def memory_search(
    query: str,
    domain: str | None = None,
    type: str | None = None,
    entity: str | None = None,
    limit: int = 10,
    auto_index: bool = True,
) -> list[dict[str, Any]]:
    """Search. Returns list of hit dicts (score, path, rel_path, snippet, ...)."""
    hits = await core_search(
        query=query,
        domain=domain,
        type=type,
        entity=entity,
        limit=limit,
        auto_index=auto_index,
    )
    return [h.to_dict() for h in hits]


def run_server(
    host: str | None = None,
    port: int | None = None,
    *,
    watch: bool = True,
) -> None:
    """Start the MCP HTTP server. Blocks until the process is killed.

    When `watch` is True (default), the server's lifespan hook also spawns
    the brain/ filesystem watcher — so external file drops get indexed
    live. Running watcher inside the server guarantees a single MemSearch
    owner (solves Milvus Lite single-process lock) and a single asyncio
    loop owner (keeps memsearch's cached httpx clients usable).
    """
    settings = load_settings()
    h = host or settings.daemon_host
    p = port or settings.daemon_port

    global _watch_enabled
    _watch_enabled = watch

    mcp.run(transport="http", host=h, port=p)


if __name__ == "__main__":
    run_server()
