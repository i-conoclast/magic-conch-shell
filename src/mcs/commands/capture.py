"""`mcs capture` command — one-line memo capture via the mcs daemon.

Default path goes through the MCP daemon so the Milvus index is owned
by a single process. `--direct` bypasses the daemon for debugging or
when the daemon is intentionally offline.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from mcs.adapters.daemon_client import DaemonUnreachable, call_tool
from mcs.adapters.memory import DOMAINS, capture as core_capture
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
) -> None:
    if silent:
        console.print(str(path))
        return
    console.print(f"[green]✓[/green] [bold]{kind}[/bold] · [dim]{id_}[/dim]")
    console.print(f"  [cyan]{rel_path}[/cyan]")
    if index_warning:
        console.print(f"  [yellow]⚠[/yellow] [dim]{index_warning}[/dim]")


def _capture_direct(
    *,
    text: str,
    domain: str | None,
    entities: list[str],
    title: str | None,
    no_index: bool,
) -> tuple[str, str, str, Path, str | None]:
    """Run capture without going through the daemon. Returns display fields."""
    result = core_capture(
        text=text,
        domain=domain,
        entities=entities,
        source="typed",
        title=title,
    )
    index_warning: str | None = None
    if not no_index:
        try:
            from mcs.adapters.search import sync_file
            asyncio.run(sync_file(result.path))
        except Exception as e:
            index_warning = f"indexing skipped: {e}"

    root = load_settings().repo_root.resolve()
    try:
        rel = str(result.path.resolve().relative_to(root))
    except ValueError:
        rel = str(result.path)
    kind = "note" if domain else "signal"
    return kind, result.id, rel, result.path, index_warning


def _capture_via_daemon(
    *,
    text: str,
    domain: str | None,
    entities: list[str],
    title: str | None,
    no_index: bool,
) -> tuple[str, str, str, Path, str | None]:
    """Send capture to the daemon via MCP."""
    payload = {
        "text": text,
        "domain": domain,
        "entities": entities,
        "source": "typed",
        "title": title,
        "index": not no_index,
    }
    data = asyncio.run(call_tool("memory.capture", payload))
    kind = data.get("type") or ("note" if domain else "signal")
    warning = None if data.get("indexed") or no_index else "indexing skipped"
    return (
        kind,
        data["id"],
        data["rel_path"],
        Path(data["path"]),
        warning,
    )


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
    direct: bool = typer.Option(
        False,
        "--direct",
        help="Bypass daemon and write directly (debugging / offline mode).",
    ),
) -> None:
    """Capture a one-line memo to brain/."""
    try:
        if direct:
            fields = _capture_direct(
                text=text,
                domain=domain,
                entities=entity or [],
                title=title,
                no_index=no_index,
            )
        else:
            fields = _capture_via_daemon(
                text=text,
                domain=domain,
                entities=entity or [],
                title=title,
                no_index=no_index,
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

    kind, id_, rel, path, index_warning = fields
    _print_result(
        kind=kind,
        id_=id_,
        rel_path=rel,
        path=path,
        index_warning=index_warning,
        silent=silent,
    )
