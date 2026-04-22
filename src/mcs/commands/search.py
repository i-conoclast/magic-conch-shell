"""`mcs search` — hybrid search over brain/ via the mcs daemon."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from mcs.adapters.daemon_client import DaemonUnreachable, call_tool
from mcs.adapters.memory import DOMAINS
from mcs.adapters.search import search as core_search

console = Console()


def _truncate(text: str, max_len: int = 80) -> str:
    """One-line snippet, no embedded newlines."""
    flat = " ".join(text.split())
    if len(flat) <= max_len:
        return flat
    return flat[: max_len - 1] + "…"


def _render_table(
    hits: list[dict[str, Any]],
    query: str,
    elapsed_ms: int,
) -> None:
    header = (
        f"🔍 [cyan]{query!r}[/cyan]  "
        f"[dim]({elapsed_ms}ms · {len(hits)} results)[/dim]"
    )
    console.print(f"\n{header}\n")

    if not hits:
        console.print("  [dim]no matches[/dim]\n")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("score", justify="right", width=6)
    table.add_column("path", style="cyan", overflow="fold")
    table.add_column("snippet", overflow="fold")

    for i, h in enumerate(hits, 1):
        table.add_row(
            str(i),
            f"{float(h['score']):.3f}",
            h["rel_path"],
            _truncate(h["snippet"] or ""),
        )
    console.print(table)


def search_cmd(
    query: str = typer.Argument(..., help="Free-form query (Korean/English)."),
    domain: str | None = typer.Option(
        None, "-d", "--domain",
        help=f"Restrict to domain: {' | '.join(sorted(DOMAINS))}.",
    ),
    type_: str | None = typer.Option(
        None, "-t", "--type",
        help="Restrict by type: signal | note | daily | entity.",
    ),
    entity: str | None = typer.Option(
        None, "-e", "--entity",
        help="Post-filter: require this entity slug (e.g. people/jane-smith).",
    ),
    limit: int = typer.Option(10, "-n", "--limit", help="Max results (default 10)."),
    as_json: bool = typer.Option(False, "--json", help="Emit raw JSON (one list)."),
    no_index: bool = typer.Option(
        False, "--no-index",
        help="Skip incremental re-index before search.",
    ),
    direct: bool = typer.Option(
        False, "--direct",
        help="Bypass daemon and query the local engine directly.",
    ),
) -> None:
    """Hybrid search over brain/ (vector + keyword via memsearch)."""
    t0 = time.time()
    try:
        if direct:
            raw = asyncio.run(
                core_search(
                    query,
                    domain=domain,
                    type=type_,
                    entity=entity,
                    limit=limit,
                    auto_index=not no_index,
                )
            )
            hits = [h.to_dict() for h in raw]
        else:
            hits = asyncio.run(
                call_tool(
                    "memory.search",
                    {
                        "query": query,
                        "domain": domain,
                        "type": type_,
                        "entity": entity,
                        "limit": limit,
                        "auto_index": not no_index,
                    },
                )
            )
    except ValueError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=2) from e
    except DaemonUnreachable as e:
        console.print(f"[red]✗[/red] {e}")
        console.print(
            "  [dim]tip: `mcs search --direct` queries the engine without the daemon.[/dim]"
        )
        raise typer.Exit(code=3) from e

    elapsed_ms = int((time.time() - t0) * 1000)

    if as_json:
        typer.echo(json.dumps(hits, ensure_ascii=False, indent=2))
        return

    _render_table(hits, query=query, elapsed_ms=elapsed_ms)
