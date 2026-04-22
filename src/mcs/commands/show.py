"""`mcs show <id>` — read a brain/ memo by id or path.

Routes through the daemon by default; `--direct` uses the local resolver.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from mcs.adapters.daemon_client import DaemonUnreachable, call_tool
from mcs.adapters.memory import MemoAmbiguous, MemoNotFound, load_memo
from mcs.config import load_settings

console = Console()


def _format_candidates(paths: list[str]) -> Table:
    settings = load_settings()
    root = settings.repo_root.resolve()
    t = Table(show_header=True, header_style="bold", title="candidates")
    t.add_column("#", justify="right", style="dim", width=3)
    t.add_column("path", style="cyan")
    for i, p in enumerate(paths, 1):
        try:
            rel = str(Path(p).resolve().relative_to(root))
        except ValueError:
            rel = p
        t.add_row(str(i), rel)
    return t


def _render(memo: dict[str, Any]) -> None:
    meta_lines = [
        f"[bold cyan]{memo['rel_path']}[/bold cyan]",
        f"[dim]id:[/dim] {memo['id']}   "
        f"[dim]type:[/dim] {memo['type']}   "
        f"[dim]domain:[/dim] {memo['domain'] or '—'}",
    ]
    if memo.get("created_at"):
        meta_lines.append(f"[dim]created:[/dim] {memo['created_at']}")
    if memo.get("source"):
        meta_lines.append(f"[dim]source:[/dim] {memo['source']}")
    if memo.get("entities"):
        meta_lines.append(
            "[dim]entities:[/dim] " + ", ".join(memo["entities"])
        )
    console.print(Panel("\n".join(meta_lines), border_style="dim"))

    body = (memo.get("body") or "").strip()
    if body:
        console.print(Markdown(body))
    else:
        console.print("[dim](empty body)[/dim]")


def show_cmd(
    query: str = typer.Argument(..., help="Slug ('2026-04-22-foo') or relative path."),
    as_json: bool = typer.Option(False, "--json", help="Emit raw JSON."),
    direct: bool = typer.Option(
        False, "--direct",
        help="Resolve locally instead of calling the daemon.",
    ),
) -> None:
    """Read a single brain/ memo."""
    if direct:
        try:
            memo = load_memo(query)
        except MemoNotFound as e:
            console.print(f"[red]✗[/red] {e}")
            raise typer.Exit(code=4)
        except MemoAmbiguous as e:
            console.print(f"[yellow]⚠[/yellow] {e}")
            console.print(_format_candidates([str(p) for p in e.candidates]))
            raise typer.Exit(code=5)

        data = {
            "found": True,
            "id": memo.id,
            "type": memo.type,
            "domain": memo.domain,
            "entities": memo.entities,
            "created_at": memo.created_at,
            "source": memo.source,
            "rel_path": memo.rel_path,
            "path": str(memo.path),
            "body": memo.body,
        }
    else:
        try:
            data = asyncio.run(call_tool("memory.show", {"query": query}))
        except DaemonUnreachable as e:
            console.print(f"[red]✗[/red] {e}")
            console.print(
                "  [dim]tip: `mcs show <query> --direct` bypasses the daemon.[/dim]"
            )
            raise typer.Exit(code=3) from e

    if as_json:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if not data.get("found"):
        console.print(f"[red]✗[/red] {data.get('reason', 'not found')}")
        cands = data.get("candidates") or []
        if cands:
            console.print(_format_candidates(cands))
            raise typer.Exit(code=5)
        raise typer.Exit(code=4)

    _render(data)
