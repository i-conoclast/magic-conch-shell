"""Filesystem watcher — auto-ingest markdown drops under brain/.

Scope: brain/signals/ and brain/domains/ only (Day 5 decision #1).
Events fire when a user creates/modifies a .md file from an external
editor (iA Writer, VS Code, direct shell write, etc.).

Pipeline per event:
  1. Ignore non-.md / hidden / non-scoped paths.
  2. Debounce repeated events on the same path (~500ms).
  3. Supplement frontmatter if missing (source=file-watcher).
  4. Call MemSearch.index_file() so the memo is searchable immediately.

Deletion events remove the source from the index via MemSearch.remove
when available; otherwise we fall back to a fresh index(force=False).
"""
from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from mcs.adapters.memory import supplement_frontmatter
from mcs.adapters.search import get_engine
from mcs.config import load_settings


# The main-thread asyncio loop that owns MemSearch's httpx clients.
# Watcher callbacks run in watchdog's observer threads, so they submit
# coroutines back to this loop via run_coroutine_threadsafe instead of
# creating their own loops (which would orphan the cached clients).
_loop_lock = threading.Lock()
_main_loop: asyncio.AbstractEventLoop | None = None


def bind_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Register the server's asyncio loop for cross-thread dispatch."""
    global _main_loop
    with _loop_lock:
        _main_loop = loop


def get_main_loop() -> asyncio.AbstractEventLoop | None:
    """Return the bound server loop (None if not yet registered)."""
    with _loop_lock:
        return _main_loop


def _dispatch(coro: Any, *, timeout: float = 30.0) -> Any:
    """Run a coroutine on the bound main loop from a watcher thread."""
    with _loop_lock:
        loop = _main_loop
    if loop is None or loop.is_closed():
        # No server loop bound — fall back to a private loop. This path
        # is only reached in standalone / test scenarios.
        return asyncio.run(coro)
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=timeout)


# Path components we refuse to touch even if a user drops files there.
_IGNORED_PARTS = frozenset({".git", ".brain", "node_modules", "__pycache__"})


def _is_scoped(brain: Path, path: Path) -> bool:
    """True if `path` is under brain/signals/ or brain/domains/ and is a .md."""
    if path.suffix.lower() != ".md":
        return False
    if path.name.startswith("."):
        return False
    # Editor atomic-save backup pattern (e.g. `2026-05-02~.md` from
    # Obsidian/Vim/Emacs writing to `<stem>~.md` and then renaming to
    # `<stem>.md`). Catching the file during its brief existence would
    # rewrite frontmatter with id="<stem>~" and fire webhooks for a
    # phantom capture id, leading to "no brain file with id" errors when
    # the extractor skill tries to load the (already-renamed-away) file.
    if path.stem.endswith("~"):
        return False
    try:
        rel = path.resolve().relative_to(brain.resolve())
    except ValueError:
        return False
    parts = rel.parts
    if any(p in _IGNORED_PARTS for p in parts):
        return False
    if not parts:
        return False
    head = parts[0]
    return head in ("signals", "domains")


class _BrainEventHandler(FileSystemEventHandler):
    """Routes watchdog events through our supplement → index pipeline."""

    def __init__(
        self,
        brain: Path,
        *,
        debounce_ms: int = 500,
        on_indexed: Callable[[str, Path], None] | None = None,
    ) -> None:
        self.brain = brain
        self.debounce_s = debounce_ms / 1000.0
        self.on_indexed = on_indexed
        self._last_fire: dict[Path, float] = {}
        self._lock = threading.Lock()

    # ─── debounce ───────────────────────────────────────────────────

    def _should_skip(self, path: Path) -> bool:
        now = time.monotonic()
        with self._lock:
            prev = self._last_fire.get(path)
            if prev is not None and (now - prev) < self.debounce_s:
                return True
            self._last_fire[path] = now
        return False

    # ─── handlers ───────────────────────────────────────────────────

    def _handle_upsert(self, path: Path) -> None:
        if not _is_scoped(self.brain, path):
            return
        if self._should_skip(path):
            return
        # Supplement frontmatter best-effort; skip gracefully on error
        # so indexing still runs on the raw body.
        try:
            supplement_frontmatter(path)
        except Exception as e:
            if self.on_indexed:
                self.on_indexed("supplement-failed", path)
            else:
                print(f"⚠ supplement failed for {path}: {e}")
        # Dispatch index_file onto the server's main event loop so the
        # cached httpx clients stay bound to one loop.
        try:
            _dispatch(get_engine().index_file(str(path)))
        except Exception as e:
            if self.on_indexed:
                self.on_indexed("index-failed", path)
            else:
                print(f"⚠ index failed for {path}: {e}")
            return
        if self.on_indexed:
            self.on_indexed("indexed", path)

    def _handle_delete(self, path: Path) -> None:
        if not _is_scoped(self.brain, path):
            return
        # memsearch 0.3 has no public delete-by-source yet; next full
        # index(force=False) will leave the removed entries orphaned.
        # We log the event; cleanup is deferred to `mcs reindex`.
        if self.on_indexed:
            self.on_indexed("deleted", path)

    # watchdog hooks
    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._handle_upsert(Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._handle_upsert(Path(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        # Treat the destination like a create; source is orphaned (see above).
        dest = getattr(event, "dest_path", None)
        if dest:
            self._handle_upsert(Path(dest))
        self._handle_delete(Path(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._handle_delete(Path(event.src_path))


def start_watcher(
    *,
    debounce_ms: int = 500,
    on_indexed: Callable[[str, Path], None] | None = None,
) -> tuple[Any, _BrainEventHandler]:
    """Launch a watchdog Observer scoped to brain/signals + brain/domains.

    Returns (observer, handler). Caller owns the lifecycle: call
    observer.stop() + observer.join() to shut down cleanly.
    """
    settings = load_settings()
    brain = settings.brain_dir.resolve()
    (brain / "signals").mkdir(parents=True, exist_ok=True)
    (brain / "domains").mkdir(parents=True, exist_ok=True)

    handler = _BrainEventHandler(
        brain,
        debounce_ms=debounce_ms,
        on_indexed=on_indexed,
    )
    observer = Observer()
    observer.schedule(handler, str(brain / "signals"), recursive=False)
    observer.schedule(handler, str(brain / "domains"), recursive=True)
    observer.start()
    return observer, handler
