"""`mcs log <template>` — structured capture via template (FR-A2).

Walks the template's field list interactively, coerces the inputs,
and routes the finished record to the daemon for writing + indexing.
`--direct` falls back to the in-process adapter for offline/debug use.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from mcs.adapters.daemon_client import DaemonUnreachable, call_tool
from mcs.adapters.memory import capture_structured as core_capture_structured
from mcs.adapters.search import sync_file
from mcs.adapters.templates import (
    TemplateError,
    list_templates,
    load_template,
)
from mcs.config import load_settings

console = Console()


def _print_template_list() -> None:
    names = list_templates()
    if not names:
        console.print("[dim]no templates in templates/[/dim]")
        return
    t = Table(show_header=True, header_style="bold")
    t.add_column("template")
    t.add_column("domain", style="dim")
    t.add_column("fields", style="dim")
    for name in names:
        try:
            tpl = load_template(name)
            t.add_row(
                name,
                tpl.domain,
                ", ".join(f.name for f in tpl.fields) or "—",
            )
        except TemplateError as e:
            t.add_row(name, "[red]error[/red]", str(e))
    console.print(t)


def _prompt_fields(tpl) -> dict[str, str]:
    """Walk the template's field list; return raw string answers."""
    console.print(
        f"\n[bold cyan]{tpl.name}[/bold cyan] "
        f"[dim](domain={tpl.domain}, {len(tpl.fields)} fields — blank = skip)[/dim]\n"
    )
    answers: dict[str, str] = {}
    for f in tpl.fields:
        prompt = f.prompt
        if f.kind == "enum":
            prompt = f"{prompt} {f.values}"
        raw = typer.prompt(prompt, default="", show_default=False)
        answers[f.name] = raw
    return answers


def log_cmd(
    template: str | None = typer.Argument(
        None,
        help="Template name (omit to list available templates).",
    ),
    title: str | None = typer.Option(
        None, "-t", "--title",
        help="Human-readable slug (else YYYY-MM-DD-HHmmss).",
    ),
    field: list[str] | None = typer.Option(
        None, "-f", "--field",
        help="Non-interactive field, repeatable: -f key=value. "
             "List values: -f key=a,b,c",
    ),
    no_index: bool = typer.Option(
        False, "--no-index",
        help="Skip immediate embedding.",
    ),
    direct: bool = typer.Option(
        False, "--direct",
        help="Bypass daemon; use local adapter.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit raw JSON result."),
) -> None:
    """Capture a structured record from a template."""
    if not template:
        _print_template_list()
        return

    try:
        tpl = load_template(template)
    except TemplateError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=2)

    # Collect field values: -f overrides; prompt for any not supplied.
    overrides: dict[str, str] = {}
    for entry in field or []:
        if "=" not in entry:
            console.print(f"[red]✗[/red] bad -f value {entry!r} (expected key=value)")
            raise typer.Exit(code=2)
        k, v = entry.split("=", 1)
        overrides[k.strip()] = v

    # If any override is present we skip prompting to stay non-interactive.
    if overrides:
        answers: dict[str, Any] = overrides
    else:
        answers = _prompt_fields(tpl)

    if direct:
        try:
            result = core_capture_structured(
                template=template, fields=answers, title=title,
            )
        except TemplateError as e:
            console.print(f"[red]✗[/red] {e}")
            raise typer.Exit(code=2)

        indexed = False
        if not no_index:
            try:
                asyncio.run(sync_file(result.path))
                indexed = True
            except Exception:
                indexed = False

        settings = load_settings()
        try:
            rel = str(result.path.resolve().relative_to(settings.repo_root.resolve()))
        except ValueError:
            rel = str(result.path)
        data = {
            "path": str(result.path),
            "rel_path": rel,
            "id": result.id,
            "type": result.type,
            "domain": result.domain,
            "indexed": indexed,
        }
    else:
        try:
            data = asyncio.run(
                call_tool(
                    "memory.capture_structured",
                    {
                        "template": template,
                        "fields": answers,
                        "title": title,
                        "index": not no_index,
                    },
                )
            )
        except DaemonUnreachable as e:
            console.print(f"[red]✗[/red] {e}")
            console.print(
                "  [dim]tip: `mcs log ... --direct` bypasses the daemon.[/dim]"
            )
            raise typer.Exit(code=3) from e
        if "error" in data:
            console.print(f"[red]✗[/red] {data['error']}")
            raise typer.Exit(code=2)

    if as_json:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return

    console.print(
        f"\n[green]✓[/green] [bold]{data['type']}[/bold] · "
        f"[dim]{data['id']}[/dim]"
    )
    console.print(f"  [cyan]{data['rel_path']}[/cyan]")
    if not data.get("indexed") and not no_index:
        console.print("  [yellow]⚠[/yellow] [dim]indexing skipped[/dim]")
