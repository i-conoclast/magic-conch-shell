"""`mcs brief [date]` — morning brief + interactive daily plan.

Two-phase orchestration (channel-agnostic — same skills work via
iMessage through Hermes's BlueBubbles adapter):

  Phase A: morning-brief skill (single-shot)
    → assistant text rendered, brain/daily/…md ## 🌅 section saved.

  Phase B: daily-plan skill (interactive REPL)
    → user iterates 3–5 turns, confirms with 'ok' / '확정' / 'go'.
    → on confirm, Notion daily_tasks rows are created and
      brain/daily/…md ## 📋 Today's Plan is appended.
    → on cancel (empty / 'quit' / '나중에'), nothing is pushed.

Flags:
  --skip-plan   Only run morning-brief (Phase A) and stop.
  --raw         Skip rich markdown rendering for Phase A.
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
    plan_session_name,
    run_skill,
)

console = Console()

_EXIT_WORDS = frozenset(
    {"quit", "exit", "q", "그만", "나갈게", "끝", "cancel", "취소", "나중에", "later"}
)


def _run_brief_phase(date: str | None, raw: bool) -> None:
    session = brief_session_name(date)
    opener = date if date else "today"

    console.print(f"[dim]brief session:[/dim] [cyan]{session}[/cyan]")
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
            "[yellow]empty brief — the skill may have failed silently.[/yellow]"
        )
        raise typer.Exit(code=1)

    console.print()
    if raw:
        console.print(text)
    else:
        console.print(Markdown(text))


def _run_plan_phase(date: str | None) -> None:
    session = plan_session_name(date)
    opener = date if date else "today"

    console.print()
    console.print("[bold]━━━ Daily Plan ━━━[/bold]")
    console.print(f"[dim]plan session:[/dim] [cyan]{session}[/cyan]")
    console.print(
        "[dim]edit until you're happy; 'ok' / '확정' / 'go' to push,"
        " 'cancel' / '취소' to bail.[/dim]\n"
    )

    user_msg: str | None = opener
    while True:
        if not user_msg:
            try:
                user_msg = typer.prompt("you", default="", show_default=False)
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]plan cancelled.[/dim]")
                return

        if not user_msg.strip() or user_msg.strip().lower() in _EXIT_WORDS:
            console.print("[dim]plan cancelled.[/dim]")
            return

        try:
            result = asyncio.run(
                run_skill(
                    skill="daily-plan",
                    opener=user_msg,
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
        except KeyboardInterrupt:
            console.print("\n[dim]plan interrupted.[/dim]")
            return

        reply = (result.get("text") or "").strip()
        if reply:
            console.print(f"\n[bold cyan]conch[/bold cyan]\n{reply}\n")
        else:
            console.print(
                "[dim](no visible reply — skill may have ended silently)[/dim]"
            )

        user_msg = None   # next iteration re-prompts


def brief_cmd(
    date: str | None = typer.Argument(
        None, help="KST date (YYYY-MM-DD). Default: today.",
    ),
    skip_plan: bool = typer.Option(
        False, "--skip-plan",
        help="Only run morning-brief; don't enter the daily-plan loop.",
    ),
    raw: bool = typer.Option(
        False, "--raw",
        help="Print the brief as raw markdown (no rich rendering).",
    ),
) -> None:
    """Run the morning brief, then interactively confirm today's plan."""
    _run_brief_phase(date, raw)
    if skip_plan:
        return
    _run_plan_phase(date)
