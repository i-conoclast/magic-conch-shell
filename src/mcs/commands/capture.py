"""`mcs capture` command — one-line memo capture."""
from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from mcs.adapters.memory import DOMAINS, capture as core_capture
from mcs.config import load_settings

console = Console()


def capture_cmd(
    text: str = typer.Argument(..., help="Memo text."),
    domain: str | None = typer.Option(
        None,
        "-d",
        "--domain",
        help=f"Domain: {' | '.join(sorted(DOMAINS))}. Omit → signals/.",
    ),
    entity: list[str] | None = typer.Option(
        None,
        "-e",
        "--entity",
        help="Entity slug to link (repeatable). Example: -e people/jane-smith",
    ),
    title: str | None = typer.Option(
        None,
        "-t",
        "--title",
        help="Readable slug title (else auto-timestamp).",
    ),
    silent: bool = typer.Option(False, "-s", "--silent", help="Suppress confirmation."),
    no_index: bool = typer.Option(
        False,
        "--no-index",
        help="Skip immediate embedding (picked up on next `mcs search`).",
    ),
) -> None:
    """Capture a one-line memo to brain/."""
    try:
        result = core_capture(
            text=text,
            domain=domain,
            entities=entity or [],
            source="typed",
            title=title,
        )
    except ValueError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=2) from e

    index_warning: str | None = None
    if not no_index:
        try:
            from mcs.adapters.search import sync_file
            asyncio.run(sync_file(result.path))
        except Exception as e:
            # capture itself succeeded — degrade gracefully on embedding failure.
            index_warning = f"indexing skipped: {e}"

    if silent:
        console.print(str(result.path))
        return

    # rich 표시
    kind = "note" if domain else "signal"
    console.print(
        f"[green]✓[/green] [bold]{kind}[/bold] · "
        f"[dim]{result.id}[/dim]"
    )
    root = load_settings().repo_root.resolve()
    try:
        display = result.path.resolve().relative_to(root)
    except ValueError:
        display = result.path
    console.print(f"  [cyan]{display}[/cyan]")
    if index_warning:
        console.print(f"  [yellow]⚠[/yellow] [dim]{index_warning}[/dim]")
