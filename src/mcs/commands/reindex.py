"""`mcs reindex` — rebuild brain/ indexes (FR-I2 / F-81).

Two underlying jobs:
- vectors:   MemSearch full re-embed (`MemSearch.index(force=True)`).
- backlinks: re-derive every entity profile's auto section.

Daemon-mediated by default — the daemon owns the Milvus Lite database
exclusively (server.py docstring), so running force-reindex from a
side-process would deadlock on the single-writer lock. `--direct` is
provided for the offline-recovery case where the daemon won't start.
"""
from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console

from mcs.adapters.daemon_client import DaemonUnreachable, call_tool

console = Console()


def reindex_cmd(
    vectors: bool = typer.Option(
        True,
        "--vectors/--no-vectors",
        help="Full re-embed of brain/ via MemSearch (default on).",
    ),
    backlinks: bool = typer.Option(
        True,
        "--backlinks/--no-backlinks",
        help="Re-derive entity Back-links sections from frontmatter (default on).",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit raw JSON."),
    direct: bool = typer.Option(
        False,
        "--direct",
        help=(
            "Bypass the daemon. Only safe when the daemon is stopped — "
            "Milvus Lite is single-writer."
        ),
    ),
) -> None:
    """Rebuild brain/ indexes after schema upgrades or corruption."""
    if not vectors and not backlinks:
        console.print(
            "[yellow]⚠[/yellow] nothing to do — pass at least one of "
            "[cyan]--vectors[/cyan] / [cyan]--backlinks[/cyan]."
        )
        raise typer.Exit(code=2)

    try:
        result = asyncio.run(_run(vectors, backlinks, direct))
    except DaemonUnreachable as e:
        console.print(f"[red]✗[/red] {e}")
        console.print(
            "  [dim]tip: stop the daemon (`mcs daemon stop`) and re-run with --direct.[/dim]"
        )
        raise typer.Exit(code=3) from e

    if as_json:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if "error" in result:
        console.print(f"[red]✗[/red] {result['error']}")
        raise typer.Exit(code=2)

    if vectors:
        n = result.get("vectors")
        console.print(
            f"[green]✓[/green] vectors re-embedded: [bold]{n}[/bold] chunks"
        )
    if backlinks:
        n = result.get("backlinks")
        console.print(
            f"[green]✓[/green] back-links re-derived: [bold]{n}[/bold] (entity, record) pairs"
        )


async def _run(vectors: bool, backlinks: bool, direct: bool) -> dict:
    if direct:
        # Local fallback. Daemon must be stopped — we don't double-check
        # because a Milvus lock failure is its own loud error.
        out: dict = {"vectors": None, "backlinks": None}
        if vectors:
            from mcs.adapters.search import rebuild_all
            out["vectors"] = await rebuild_all()
        if backlinks:
            from mcs.adapters.entity import rebuild_backlinks
            out["backlinks"] = rebuild_backlinks()
        return out
    return await call_tool(
        "memory.reindex",
        {"vectors": vectors, "backlinks": backlinks},
    )
