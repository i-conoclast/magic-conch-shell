"""`mcs inbox` — generic suggestion approval surface (FR-G3).

Subcommands:
  list                       Show pending items across all sources
  approve <type>/<id> [--extra k=v ...]  Promote one item
  reject <type>/<id> [-r reason]         Reject + log
  defer <type>/<id>                       No-op (item stays for next session)

Type prefix in the id (e.g. `entity-draft/people/jane-smith`) keeps the
CLI single-arg friendly; type-only forms also work via --type.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from mcs.adapters import inbox as inbox_mod
from mcs.adapters.daemon_client import DaemonUnreachable, call_tool


app = typer.Typer(name="inbox", help="Review pending suggestions across all sources.")
console = Console()


def _run(coro):
    try:
        return asyncio.run(coro)
    except DaemonUnreachable as e:
        console.print(f"[red]✗[/red] {e}")
        console.print("  [dim]tip: add --direct to bypass the daemon.[/dim]")
        raise typer.Exit(code=3) from e


def _split_typed_id(raw: str, type_flag: str | None) -> tuple[str, str]:
    """Parse `<type>/<id>` (e.g. entity-draft/people/jane-smith) or fallback."""
    if type_flag:
        return type_flag, raw
    if "/" not in raw:
        raise typer.BadParameter(
            "id must be `<type>/<id>` or pass --type explicitly."
        )
    head, rest = raw.split("/", 1)
    return head, rest


# ─── list ──────────────────────────────────────────────────────────────

async def _fetch_list(item_type: str | None, direct: bool) -> list[dict[str, Any]]:
    if direct:
        return [it.to_dict() for it in inbox_mod.list_pending(item_type=item_type)]
    return await call_tool("memory.inbox_list", {"item_type": item_type})


@app.command("list")
def list_cmd(
    item_type: str | None = typer.Option(
        None, "-t", "--type",
        help="Filter to one source (e.g. entity-draft, skill-promotion).",
    ),
    as_json: bool = typer.Option(False, "--json"),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """List every pending item across all sources, newest first."""
    data = _run(_fetch_list(item_type, direct))

    if as_json:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if not data:
        console.print("[dim]inbox empty.[/dim]")
        return

    title = "Inbox"
    if item_type:
        title += f" · type={item_type}"

    t = Table(title=title, show_header=True, header_style="bold")
    t.add_column("type", style="dim")
    t.add_column("id", style="cyan")
    t.add_column("summary")
    t.add_column("created", style="dim")
    for item in data:
        t.add_row(
            item.get("type", "?"),
            item.get("id", "?"),
            item.get("summary", ""),
            (item.get("created_at") or "")[:19],
        )
    console.print(t)


# ─── approve / reject / defer ──────────────────────────────────────────

async def _fetch_act(
    item_type: str,
    item_id: str,
    action: str,
    extra: dict[str, Any] | None,
    reason: str | None,
    direct: bool,
) -> dict[str, Any]:
    if direct:
        kwargs: dict[str, Any] = {}
        if extra is not None:
            kwargs["extra"] = extra
        if reason is not None:
            kwargs["reason"] = reason
        try:
            return inbox_mod.act(item_type, item_id, action, **kwargs)
        except inbox_mod.InboxError as e:
            return {"error": str(e)}
    return await call_tool(
        "memory.inbox_act",
        {
            "item_type": item_type,
            "item_id": item_id,
            "action": action,
            "extra": extra,
            "reason": reason,
        },
    )


def _parse_set_options(raw: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in raw:
        if "=" not in entry:
            raise typer.BadParameter(f"--set expects key=value, got {entry!r}")
        k, v = entry.split("=", 1)
        out[k.strip()] = v.strip()
    return out


@app.command("approve")
def approve_cmd(
    target: str = typer.Argument(
        ...,
        help="`<type>/<id>` (e.g. entity-draft/people/jane-smith).",
    ),
    item_type: str | None = typer.Option(None, "-t", "--type"),
    set_field: list[str] = typer.Option(
        [], "--set",
        help="Type-specific extra field, key=value (repeatable).",
    ),
    as_json: bool = typer.Option(False, "--json"),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """Approve / confirm one inbox item."""
    typ, item_id = _split_typed_id(target, item_type)
    extra = _parse_set_options(set_field) or None
    data = _run(_fetch_act(typ, item_id, "approve", extra, None, direct))

    if as_json:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if "error" in data:
        console.print(f"[red]✗[/red] {data['error']}")
        raise typer.Exit(code=4)
    console.print(f"[green]✓[/green] {typ}/{item_id} → {data.get('status', 'ok')}")


@app.command("reject")
def reject_cmd(
    target: str = typer.Argument(...),
    item_type: str | None = typer.Option(None, "-t", "--type"),
    reason: str | None = typer.Option(None, "-r", "--reason"),
    as_json: bool = typer.Option(False, "--json"),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """Reject + log."""
    typ, item_id = _split_typed_id(target, item_type)
    data = _run(_fetch_act(typ, item_id, "reject", None, reason, direct))

    if as_json:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if "error" in data:
        console.print(f"[red]✗[/red] {data['error']}")
        raise typer.Exit(code=4)
    console.print(
        f"[yellow]⊘[/yellow] {typ}/{item_id} rejected"
        + (f" — {reason}" if reason else "")
    )


@app.command("defer")
def defer_cmd(
    target: str = typer.Argument(...),
    item_type: str | None = typer.Option(None, "-t", "--type"),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """No-op marker — item stays in the queue. Mostly there for symmetry."""
    typ, item_id = _split_typed_id(target, item_type)
    data = _run(_fetch_act(typ, item_id, "defer", None, None, direct))
    if "error" in data:
        console.print(f"[red]✗[/red] {data['error']}")
        raise typer.Exit(code=4)
    console.print(f"[dim]→[/dim] {typ}/{item_id} deferred")
