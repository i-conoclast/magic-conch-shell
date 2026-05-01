"""`mcs entity` — manual CRUD over brain/entities/.

Subcommands:
  list             Active entities (and/or drafts) with kind filter
  show <slug>      Profile body + meta + back-links section
  confirm <slug>   Promote a draft to active (with optional --role/--company/...)
  reject <slug>    Delete a draft and append to .brain/rejected-entities.jsonl

Auto-detection (FR-C1) lives in the Hermes `entity-extract` skill;
these CLI commands cover the manual override + approval paths.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from mcs.adapters import entity as entity_mod
from mcs.adapters.daemon_client import DaemonUnreachable, call_tool


app = typer.Typer(name="entity", help="Manage entity drafts/profiles under brain/entities/.")
console = Console()


# ─── dispatch helpers ──────────────────────────────────────────────────

def _run(coro):
    try:
        return asyncio.run(coro)
    except DaemonUnreachable as e:
        console.print(f"[red]✗[/red] {e}")
        console.print("  [dim]tip: add --direct to bypass the daemon.[/dim]")
        raise typer.Exit(code=3) from e


def _ref_to_dict(ref: entity_mod.EntityRef) -> dict[str, Any]:
    return {
        "kind": ref.kind,
        "slug": ref.slug,
        "qualified": ref.qualified,
        "name": ref.name,
        "status": ref.status,
        "path": str(ref.path),
        "meta": ref.meta,
    }


async def _fetch_list(
    kind: str | None, drafts_only: bool, include_drafts: bool, direct: bool
) -> list[dict[str, Any]]:
    if direct:
        if drafts_only:
            refs = entity_mod.list_drafts(kind=kind)
        else:
            refs = entity_mod.list_entities(
                kind=kind, include_drafts=include_drafts
            )
        return [_ref_to_dict(r) for r in refs]

    if drafts_only:
        return await call_tool("memory.entity_list_drafts", {"kind": kind})
    # The daemon doesn't expose a unified list yet; emulate it for non-drafts.
    raise typer.BadParameter(
        "active listing via the daemon is not exposed yet — use --direct."
    )


async def _fetch_get(slug: str, direct: bool) -> dict[str, Any]:
    if direct:
        try:
            ref = entity_mod.resolve_entity(slug)
        except entity_mod.EntityNotFound as e:
            return {"found": False, "reason": str(e), "candidates": []}
        except entity_mod.EntityAmbiguous as e:
            return {
                "found": False,
                "reason": str(e),
                "candidates": list(e.candidates),
            }
        body = ref.path.read_text(encoding="utf-8")
        return {"found": True, **_ref_to_dict(ref), "body": body}
    return await call_tool("memory.entity_get", {"slug": slug})


async def _do_confirm(
    slug: str, extra: dict[str, Any], direct: bool
) -> dict[str, Any]:
    if direct:
        try:
            ref = entity_mod.confirm(slug, extra=extra or None)
        except entity_mod.EntityError as e:
            return {"error": str(e)}
        return _ref_to_dict(ref)
    return await call_tool(
        "memory.entity_confirm", {"slug": slug, "extra": extra or None}
    )


async def _do_reject(slug: str, reason: str | None, direct: bool) -> dict[str, Any]:
    if direct:
        try:
            return entity_mod.reject(slug, reason=reason)
        except entity_mod.EntityError as e:
            return {"error": str(e)}
    return await call_tool(
        "memory.entity_reject", {"slug": slug, "reason": reason}
    )


# ─── list ──────────────────────────────────────────────────────────────

@app.command("list")
def list_cmd(
    kind: str | None = typer.Option(
        None, "-k", "--kind",
        help="Filter by kind (people | companies | jobs | books | ...).",
    ),
    drafts: bool = typer.Option(
        False, "--drafts", help="Show only pending drafts (approval inbox)."
    ),
    include_drafts: bool = typer.Option(
        False, "--all", help="Include drafts alongside active profiles."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON."),
    direct: bool = typer.Option(False, "--direct", help="Bypass the daemon."),
) -> None:
    """List entities. Defaults to active only; use --drafts for the inbox."""
    if drafts and include_drafts:
        raise typer.BadParameter("--drafts and --all are mutually exclusive.")

    data = _run(_fetch_list(kind, drafts, include_drafts, direct))

    if as_json:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if not data:
        console.print("[dim]no matching entities.[/dim]")
        return

    title = "Drafts" if drafts else "Entities"
    if kind:
        title += f" · kind={kind}"
    if include_drafts:
        title += " · +drafts"

    t = Table(title=title, show_header=True, header_style="bold")
    t.add_column("status", style="dim", width=6)
    t.add_column("kind", style="dim")
    t.add_column("slug", style="cyan")
    t.add_column("name")
    t.add_column("meta", style="dim")

    for ref in data:
        meta_bits = []
        for k in ("role", "company", "url", "relation"):
            v = (ref.get("meta") or {}).get(k)
            if v:
                meta_bits.append(f"{k}={v}")
        t.add_row(
            ref.get("status", "?"),
            ref.get("kind", "?"),
            ref.get("slug", "?"),
            ref.get("name", "?"),
            ", ".join(meta_bits) or "—",
        )
    console.print(t)


# ─── show ──────────────────────────────────────────────────────────────

@app.command("show")
def show_cmd(
    slug: str = typer.Argument(
        ..., help="Entity reference (e.g. people/jane-smith or bare slug)."
    ),
    as_json: bool = typer.Option(False, "--json"),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """Show an entity profile (active or draft)."""
    data = _run(_fetch_get(slug, direct))

    if as_json:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if not data.get("found", False):
        console.print(f"[red]✗[/red] {data.get('reason', 'not found')}")
        for cand in data.get("candidates") or []:
            console.print(f"  [dim]candidate:[/dim] {cand}")
        raise typer.Exit(code=4)

    header_lines = [
        f"[bold cyan]{data['qualified']}[/bold cyan]",
        f"{data['name']} · {data['status']}",
    ]
    meta = data.get("meta") or {}
    extras = [f"{k}={v}" for k, v in meta.items() if k not in {
        "kind", "slug", "name", "status",
    }]
    if extras:
        header_lines.append(f"[dim]{' · '.join(extras)}[/dim]")
    console.print(Panel("\n".join(header_lines), border_style="dim"))

    body = data.get("body") or ""
    # body includes the frontmatter; strip it for human display.
    if body.startswith("---"):
        parts = body.split("---", 2)
        body = parts[2] if len(parts) >= 3 else body
    console.print(Markdown(body.strip() or "_(empty)_"))


# ─── confirm ───────────────────────────────────────────────────────────

@app.command("confirm")
def confirm_cmd(
    slug: str = typer.Argument(..., help="Draft slug (e.g. people/jane-smith)."),
    role: str | None = typer.Option(None, "--role"),
    company: str | None = typer.Option(None, "--company"),
    relation: str | None = typer.Option(None, "--relation"),
    url: str | None = typer.Option(None, "--url"),
    set_field: list[str] = typer.Option(
        [],
        "--set",
        help="Free-form field, key=value (repeatable).",
    ),
    as_json: bool = typer.Option(False, "--json"),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """Promote a draft to an active entity, optionally adding fields."""
    extra: dict[str, Any] = {}
    for k, v in (("role", role), ("company", company), ("relation", relation), ("url", url)):
        if v is not None:
            extra[k] = v
    for raw in set_field:
        if "=" not in raw:
            raise typer.BadParameter(f"--set expects key=value, got {raw!r}")
        k, v = raw.split("=", 1)
        extra[k.strip()] = v.strip()

    data = _run(_do_confirm(slug, extra, direct))

    if as_json:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if "error" in data:
        console.print(f"[red]✗[/red] {data['error']}")
        raise typer.Exit(code=4)

    console.print(
        f"[green]✓[/green] {data['qualified']} → active "
        f"[dim]({data['path']})[/dim]"
    )


# ─── reject ────────────────────────────────────────────────────────────

@app.command("reject")
def reject_cmd(
    slug: str = typer.Argument(..., help="Draft slug (e.g. people/jane-smith)."),
    reason: str | None = typer.Option(None, "-r", "--reason"),
    as_json: bool = typer.Option(False, "--json"),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """Delete a draft and log it to .brain/rejected-entities.jsonl."""
    data = _run(_do_reject(slug, reason, direct))

    if as_json:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if "error" in data:
        console.print(f"[red]✗[/red] {data['error']}")
        raise typer.Exit(code=4)

    console.print(
        f"[yellow]⊘[/yellow] {data['kind']}/{data['slug']} rejected"
        + (f" — {reason}" if reason else "")
    )
