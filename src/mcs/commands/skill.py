"""`mcs skill` — manage skill-promotion drafts (FR-E5).

For now exposes one subcommand (`propose`) that creates a draft under
.brain/skill-suggestions/. The draft surfaces in `mcs inbox list` and
the inbox-approve skill alongside entity drafts, so evening retro is
the single review surface.

Auto-detection (Hermes session-log analysis) is the v1 follow-up.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from mcs.adapters import skill_suggestion as ss
from mcs.adapters.daemon_client import DaemonUnreachable, call_tool


app = typer.Typer(name="skill", help="Skill-promotion drafts (FR-E5).")
console = Console()


def _run(coro):
    try:
        return asyncio.run(coro)
    except DaemonUnreachable as e:
        console.print(f"[red]✗[/red] {e}")
        console.print("  [dim]tip: add --direct to bypass the daemon.[/dim]")
        raise typer.Exit(code=3) from e


@app.command("propose")
def propose_cmd(
    slug: str = typer.Argument(..., help="Slug for the new skill (kebab-case)."),
    name: str | None = typer.Option(
        None, "-n", "--name",
        help="Display name. Defaults to a Title Case form of `slug`.",
    ),
    summary: str | None = typer.Option(
        None, "-s", "--summary",
        help="One-line note explaining what pattern this skill captures.",
    ),
    body_file: Path | None = typer.Option(
        None, "--body",
        help="Path to a .md file whose content becomes the draft body.",
    ),
    session_id: str | None = typer.Option(
        None, "--from-session",
        help="Source Hermes session id, if known (annotation only).",
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Stage a skill-promotion draft for review in the next evening retro."""
    display_name = name or slug.replace("-", " ").title()
    body = ""
    if body_file is not None:
        if not body_file.exists():
            console.print(f"[red]✗[/red] body file not found: {body_file}")
            raise typer.Exit(code=2)
        body = body_file.read_text(encoding="utf-8")

    try:
        sug = ss.create_draft(
            slug=slug,
            name=display_name,
            body=body,
            source_session_id=session_id,
            summary=summary or "",
        )
    except (ValueError, ss.SkillSuggestionError) as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=4) from e

    if as_json:
        typer.echo(json.dumps(sug.to_dict(), ensure_ascii=False, indent=2))
        return

    console.print(
        f"[green]✓[/green] proposed → [cyan]{sug.slug}[/cyan] "
        f"[dim]({sug.path})[/dim]"
    )
    console.print(
        "  [dim]review during next evening retro or via "
        "`mcs inbox approve skill-promotion/" + sug.slug + "`.[/dim]"
    )


@app.command("list")
def list_cmd(
    as_json: bool = typer.Option(False, "--json"),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """Show pending skill-promotion drafts only (subset of `mcs inbox list`)."""
    async def _fetch() -> list[dict[str, Any]]:
        if direct:
            return [s.to_dict() for s in ss.list_drafts()]
        return await call_tool(
            "memory.inbox_list", {"item_type": "skill-promotion"}
        )

    data = _run(_fetch())
    if as_json:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if not data:
        console.print("[dim]no pending skill suggestions.[/dim]")
        return
    for entry in data:
        # Normalise both the direct (SkillSuggestion.to_dict) and the
        # daemon (InboxItem.to_dict) shapes — the latter has an `id`/`summary`
        # pair instead of slug/name.
        slug = entry.get("slug") or entry.get("id") or "?"
        name = entry.get("name") or entry.get("summary") or ""
        console.print(f"[cyan]{slug}[/cyan]  {name}")
