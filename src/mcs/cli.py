"""magic-conch-shell — CLI entry point."""
from __future__ import annotations

import typer
from rich.console import Console

from mcs.commands.capture import capture_cmd

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


def main() -> None:
    """Entry point for `mcs` script."""
    app()


if __name__ == "__main__":
    main()
