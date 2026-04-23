"""`mcs brief [date]` — morning briefing via Hermes.

Single-shot invocation of the morning-brief skill: Hermes composes
the brief, saves it to brain/daily/YYYY/MM/DD.md via MCP, and returns
the markdown text which we render to the terminal.
"""
from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.markdown import Markdown

from mcs.adapters.hermes_client import (
    HermesAuthError,
    HermesError,
    HermesUnreachable,
    brief_session_name,
    run_skill,
)

console = Console()


def brief_cmd(
    date: str | None = typer.Argument(
        None,
        help="KST date (YYYY-MM-DD). Default: today.",
    ),
    raw: bool = typer.Option(
        False, "--raw",
        help="Print the brief as raw markdown text (no rich rendering).",
    ),
) -> None:
    """Generate and save the morning briefing for the given date."""
    session = brief_session_name(date)
    opener = date if date else "today"

    console.print(f"[dim]session:[/dim] [cyan]{session}[/cyan]")
    console.print("[dim]composing brief…[/dim]")

    try:
        result = asyncio.run(
            run_skill(
                skill="morning-brief",
                opener=opener,
                conversation=session,
                timeout=240.0,
            )
        )
    except HermesUnreachable as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=3) from e
    except HermesAuthError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=4) from e
    except HermesError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=1) from e

    text = (result.get("text") or "").strip()
    if not text:
        console.print(
            "[yellow]empty response — the skill may have failed silently.[/yellow]"
        )
        raise typer.Exit(code=1)

    console.print()
    if raw:
        console.print(text)
    else:
        console.print(Markdown(text))
