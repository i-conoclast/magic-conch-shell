"""magic-conch-shell — CLI entry point."""
from __future__ import annotations

import typer
from rich.console import Console

from mcs.commands.brief import brief_cmd
from mcs.commands.capture import capture_cmd
from mcs.commands.daemon import app as daemon_app
from mcs.commands.log import log_cmd
from mcs.commands.okr import app as okr_app
from mcs.commands.search import search_cmd
from mcs.commands.show import show_cmd

app = typer.Typer(
    name="mcs",
    help="magic-conch-shell — personal life brain + agent",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()


@app.command()
def version() -> None:
    """Show version."""
    from mcs import __version__
    console.print(f"[cyan]magic-conch-shell[/cyan] [dim]v{__version__}[/dim]")


@app.command()
def hello() -> None:
    """Smoke test — the shell has spoken."""
    console.print("[bold]The shell has spoken.[/bold]")


# Register: mcs capture ...
app.command(name="capture", help="Capture a one-line memo to brain/.")(capture_cmd)
app.command(name="search", help="Hybrid search over brain/.")(search_cmd)
app.command(name="show", help="Read a brain/ memo by id or path.")(show_cmd)
app.command(name="log", help="Structured capture via template (interview, meeting, experiment).")(log_cmd)
app.command(name="brief", help="Generate morning briefing (FR-D1).")(brief_cmd)
app.add_typer(okr_app, name="okr")
app.add_typer(daemon_app, name="daemon")


def main() -> None:
    """Entry point for `mcs` script."""
    app()


if __name__ == "__main__":
    main()
