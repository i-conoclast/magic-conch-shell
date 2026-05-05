"""`mcs day [YYYY-MM-DD]` — daily journal view (FR-B3 / F-12).

Bundles the day's daily-file body + every capture (signal + note) whose
frontmatter `created_at` falls on that date. Default = today KST.

Routes through the daemon (`memory.read_daily` + `memory.list_captures`)
so the running daemon stays the single Milvus owner; `--direct` falls
back to the local adapters when the daemon is down.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from mcs.adapters.daemon_client import DaemonUnreachable, call_tool
from mcs.adapters.memory import (
    list_captures_by_date as core_list_captures_by_date,
    read_daily as core_read_daily,
)

console = Console()

_KST = ZoneInfo("Asia/Seoul")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _kst_today() -> str:
    return datetime.now(_KST).strftime("%Y-%m-%d")


async def _fetch_daily(date: str, direct: bool) -> dict[str, Any]:
    if direct:
        return core_read_daily(date)
    return await call_tool("memory.read_daily", {"date": date})


async def _fetch_captures(
    date: str, domain: str | None, direct: bool
) -> list[dict[str, Any]]:
    if direct:
        rows = core_list_captures_by_date(date, domain=domain)
        return [r.to_dict() for r in rows]
    args: dict[str, Any] = {"date": date}
    if domain is not None:
        args["domain"] = domain
    return await call_tool("memory.list_captures", args)


def _strip_frontmatter(content: str) -> str:
    """Drop a leading `---\\n...\\n---\\n` block so rendering shows the body."""
    if not content.startswith("---\n"):
        return content
    end = content.find("\n---\n", 4)
    if end == -1:
        return content
    return content[end + 5 :]


def _render_captures(rows: list[dict[str, Any]]) -> Table:
    t = Table(show_header=True, header_style="bold", title="captures")
    t.add_column("type", style="dim", width=8)
    t.add_column("domain", style="cyan", width=10)
    t.add_column("id", style="magenta")
    t.add_column("excerpt")
    for row in rows:
        t.add_row(
            str(row.get("type") or "—"),
            str(row.get("domain") or "—"),
            str(row.get("id") or ""),
            str(row.get("excerpt") or ""),
        )
    return t


def day_cmd(
    date: str = typer.Argument(
        None, help="KST date 'YYYY-MM-DD' (default: today)."
    ),
    domain: str = typer.Option(
        None, "--domain", "-d", help="Filter captures by frontmatter domain."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit raw JSON."),
    direct: bool = typer.Option(
        False, "--direct",
        help="Resolve locally instead of calling the daemon.",
    ),
) -> None:
    """Show one day's daily file + captures."""
    target = date or _kst_today()
    if not _DATE_RE.match(target):
        console.print(f"[red]✗[/red] date must be 'YYYY-MM-DD', got {target!r}")
        raise typer.Exit(code=2)

    try:
        daily, captures = asyncio.run(_gather(target, domain, direct))
    except DaemonUnreachable as e:
        console.print(f"[red]✗[/red] {e}")
        console.print(
            "  [dim]tip: `mcs day <date> --direct` bypasses the daemon.[/dim]"
        )
        raise typer.Exit(code=3) from e

    if as_json:
        typer.echo(
            json.dumps(
                {"date": target, "daily": daily, "captures": captures},
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    _render(target, daily, captures)


async def _gather(
    date: str, domain: str | None, direct: bool
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    daily_task = _fetch_daily(date, direct)
    cap_task = _fetch_captures(date, domain, direct)
    return await asyncio.gather(daily_task, cap_task)


def _render(
    date: str, daily: dict[str, Any], captures: list[dict[str, Any]]
) -> None:
    header = (
        f"[bold cyan]{date}[/bold cyan]   "
        f"[dim]captures:[/dim] {len(captures)}   "
        f"[dim]daily:[/dim] {'yes' if daily.get('exists') else 'none'}"
    )
    console.print(Panel(header, border_style="dim"))

    if daily.get("exists"):
        body = _strip_frontmatter(daily.get("content") or "").strip()
        if body:
            console.print(Markdown(body))
        else:
            console.print("[dim](daily file is empty)[/dim]")
    else:
        console.print("[dim]no daily/ entry yet for this date[/dim]")

    if captures:
        console.print(_render_captures(captures))
    else:
        console.print("[dim]no captures on this date[/dim]")
