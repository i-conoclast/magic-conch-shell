"""`mcs capture` command — one-line memo capture via the mcs daemon.

Default path goes through the MCP daemon so the Milvus index is owned
by a single process. `--direct` bypasses the daemon for debugging or
when the daemon is intentionally offline.

`--kr <kr-id>` (repeatable) links the memo to a KR: the kr-id lands in
the frontmatter `okrs:` field as lightweight back-evidence. Adding
`--increment N` also bumps the KR's `current` by N via the okr adapter
so progress stays in sync without a second command.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from mcs.adapters.daemon_client import DaemonUnreachable, call_tool
from mcs.adapters.memory import DOMAINS, capture as core_capture
from mcs.adapters.okr import (
    OKRError,
    OKRNotFound,
    get_kr as core_get_kr,
    update_kr as core_update_kr,
)
from mcs.config import load_settings

console = Console()


def _print_result(
    *,
    kind: str,
    id_: str,
    rel_path: str,
    path: Path,
    index_warning: str | None,
    silent: bool,
    kr_updates: list[str] | None = None,
    notion_line: str | None = None,
) -> None:
    if silent:
        console.print(str(path))
        return
    console.print(f"[green]✓[/green] [bold]{kind}[/bold] · [dim]{id_}[/dim]")
    console.print(f"  [cyan]{rel_path}[/cyan]")
    for line in kr_updates or []:
        console.print(f"  [dim]kr:[/dim] {line}")
    if notion_line:
        console.print(f"  [dim]notion:[/dim] {notion_line}")
    if index_warning:
        console.print(f"  [yellow]⚠[/yellow] [dim]{index_warning}[/dim]")


def _capture_direct(
    *,
    text: str,
    domain: str | None,
    entities: list[str],
    title: str | None,
    okrs: list[str],
    no_index: bool,
    no_notion: bool,
) -> tuple[str, str, str, Path, str | None, str | None]:
    """Run capture without going through the daemon.

    Returns (kind, id, rel_path, path, index_warning, notion_line).
    """
    result = core_capture(
        text=text,
        domain=domain,
        entities=entities,
        source="typed",
        title=title,
        okrs=okrs,
    )
    index_warning: str | None = None
    if not no_index:
        try:
            from mcs.adapters.search import sync_file
            asyncio.run(sync_file(result.path))
        except Exception as e:
            index_warning = f"indexing skipped: {e}"

    notion_line: str | None = None
    if not no_notion:
        try:
            from mcs.adapters import notion as notion_mod
            from mcs.adapters.notion import CaptureInput
            from mcs.adapters.okr import OKRError, OKRNotFound, get_kr

            kr_notion_ids: list[str] = []
            for kr_id in okrs:
                try:
                    kr = get_kr(kr_id)
                    if kr.notion_page_id:
                        kr_notion_ids.append(kr.notion_page_id)
                except (OKRError, OKRNotFound):
                    continue

            cap_input = CaptureInput(
                mcs_id=result.id,
                text=text,
                type=result.type,
                domain=result.domain,
                created=result.id[:10],
                entities=entities,
                source="typed",
                kr_notion_ids=kr_notion_ids,
            )
            push_res = asyncio.run(notion_mod.push_capture(cap_input))
            notion_line = f"pushed ({push_res.notion_page_id[-8:]})"
        except Exception as e:
            notion_line = f"push skipped: {type(e).__name__}"

    root = load_settings().repo_root.resolve()
    try:
        rel = str(result.path.resolve().relative_to(root))
    except ValueError:
        rel = str(result.path)
    kind = "note" if domain else "signal"
    return kind, result.id, rel, result.path, index_warning, notion_line


def _capture_via_daemon(
    *,
    text: str,
    domain: str | None,
    entities: list[str],
    title: str | None,
    okrs: list[str],
    no_index: bool,
    no_notion: bool,
) -> tuple[str, str, str, Path, str | None, str | None]:
    """Send capture to the daemon via MCP.

    Returns (kind, id, rel_path, path, index_warning, notion_line).
    """
    payload: dict[str, Any] = {
        "text": text,
        "domain": domain,
        "entities": entities,
        "okrs": okrs,
        "source": "typed",
        "title": title,
        "index": not no_index,
        "push_notion": not no_notion,
    }
    data = asyncio.run(call_tool("memory.capture", payload))
    kind = data.get("type") or ("note" if domain else "signal")
    warning = None if data.get("indexed") or no_index else "indexing skipped"

    notion_line: str | None = None
    if not no_notion:
        if data.get("notion_pushed"):
            pid = data.get("notion_page_id") or ""
            notion_line = f"pushed ({pid[-8:]})" if pid else "pushed"
        else:
            notion_line = "push skipped"

    return (
        kind,
        data["id"],
        data["rel_path"],
        Path(data["path"]),
        warning,
        notion_line,
    )


def _bump_krs(
    kr_ids: list[str], increment: float, direct: bool
) -> list[str]:
    """Add `increment` to each KR's `current`. Returns human-readable diff lines.

    Uses the daemon's MCP tool when available, falls back to direct adapter
    calls when --direct is set OR the daemon call fails mid-run.
    """
    lines: list[str] = []
    for kr_id in kr_ids:
        try:
            if direct:
                before = core_get_kr(kr_id)
                new_current = (before.current or 0.0) + increment
                after = core_update_kr(kr_id, current=new_current)
                lines.append(
                    f"{kr_id}: current {before.current:g} → {after.current:g}"
                )
            else:
                before = asyncio.run(call_tool("okr.get_kr", {"kr_id": kr_id}))
                if "error" in before:
                    lines.append(f"{kr_id}: [red]{before['error']}[/red]")
                    continue
                new_current = float(before.get("current") or 0) + increment
                after = asyncio.run(
                    call_tool(
                        "okr.update_kr",
                        {"kr_id": kr_id, "fields": {"current": new_current}},
                    )
                )
                if "error" in after:
                    lines.append(f"{kr_id}: [red]{after['error']}[/red]")
                    continue
                lines.append(
                    f"{kr_id}: current {float(before.get('current') or 0):g} "
                    f"→ {float(after['current']):g}"
                )
        except (OKRError, OKRNotFound) as e:
            lines.append(f"{kr_id}: [red]{e}[/red]")
    return lines


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
    kr: list[str] | None = typer.Option(
        None,
        "-k",
        "--kr",
        help=(
            "KR id to back-link (repeatable). Example:"
            " -k 2026-Q2-career-mle-role.kr-2"
        ),
    ),
    increment: float = typer.Option(
        0.0,
        "--increment",
        help=(
            "Bump every linked KR's `current` by this value after writing"
            " the memo (default 0 = no bump). Applies to each --kr given."
        ),
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
    no_notion: bool = typer.Option(
        False,
        "--no-notion",
        help="Skip pushing to mcs_captures Notion DB.",
    ),
    direct: bool = typer.Option(
        False,
        "--direct",
        help="Bypass daemon and write directly (debugging / offline mode).",
    ),
) -> None:
    """Capture a one-line memo to brain/."""
    okrs_list = list(kr or [])
    try:
        if direct:
            fields = _capture_direct(
                text=text,
                domain=domain,
                entities=entity or [],
                title=title,
                okrs=okrs_list,
                no_index=no_index,
                no_notion=no_notion,
            )
        else:
            fields = _capture_via_daemon(
                text=text,
                domain=domain,
                entities=entity or [],
                title=title,
                okrs=okrs_list,
                no_index=no_index,
                no_notion=no_notion,
            )
    except ValueError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=2) from e
    except DaemonUnreachable as e:
        console.print(f"[red]✗[/red] {e}")
        console.print(
            "  [dim]tip: `mcs capture --direct` runs without the daemon.[/dim]"
        )
        raise typer.Exit(code=3) from e

    kind, id_, rel, path, index_warning, notion_line = fields

    kr_updates: list[str] = []
    if okrs_list and increment:
        kr_updates = _bump_krs(okrs_list, increment, direct)

    _print_result(
        kind=kind,
        id_=id_,
        rel_path=rel,
        path=path,
        index_warning=index_warning,
        silent=silent,
        kr_updates=kr_updates,
        notion_line=notion_line,
    )
