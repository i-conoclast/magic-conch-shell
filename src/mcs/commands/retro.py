"""`mcs retro [date]` — evening retro narrative + entity inbox + capture-KR sync.

Three-phase orchestration mirroring `mcs brief`:

  Phase A: evening-retro skill (single-shot)
    → composes 4-block narrative (plan ✓/⊘, new context, KR delta,
      one-line tomorrow question), saves brain/daily/…md ## 🌙.

  Phase B: entity-approve skill (interactive REPL, FR-C2)
    → walks pending entity drafts, parses confirm/reject/defer
      directives, calls memory.entity_confirm / entity_reject.
    → exits cleanly if the inbox is empty.

  Phase C: capture-progress-sync skill (interactive REPL)
    → batch reviews today's captures vs active KRs, applies
      approved updates via okr.update_kr + memory.add_okr_link.

Flags:
  --skip-entity-approve   Skip the FR-C2 inbox phase.
  --skip-sync             Skip the capture-KR sync REPL.
  --raw                   Skip rich markdown rendering for Phase A.
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
    entity_approve_session_name,
    retro_session_name,
    run_skill,
    sync_session_name,
)

console = Console()

_EXIT_WORDS = frozenset(
    {"quit", "exit", "q", "그만", "나갈게", "끝", "cancel", "취소", "나중에", "later"}
)


def _run_retro_phase(date: str | None, raw: bool) -> None:
    session = retro_session_name(date)
    opener = date if date else "today"

    console.print(f"[dim]retro session:[/dim] [cyan]{session}[/cyan]")
    console.print("[dim]composing retro…[/dim]")

    try:
        result = asyncio.run(
            run_skill(
                skill="evening-retro",
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
            "[yellow]empty retro — the skill may have failed silently.[/yellow]"
        )
        raise typer.Exit(code=1)

    console.print()
    if raw:
        console.print(text)
    else:
        console.print(Markdown(text))


_EMPTY_INBOX_MARKERS = (
    "no entity drafts",
    "인박스 비었음",
    "인박스 0",
)


def _looks_empty_inbox(reply: str) -> bool:
    low = reply.lower()
    return any(m in low for m in _EMPTY_INBOX_MARKERS)


def _run_entity_approve_phase(date: str | None) -> None:
    session = entity_approve_session_name(date)
    opener = date if date else "today"

    console.print()
    console.print("[bold]━━━ Entity Approve ━━━[/bold]")
    console.print(f"[dim]inbox session:[/dim] [cyan]{session}[/cyan]")
    console.print(
        '[dim]reply with "1 승인", "2 거절 노이즈", "3 내일", "all 승인", '
        '"1-3 승인" — empty/cancel to exit.[/dim]\n'
    )

    user_msg: str | None = opener
    first_turn = True
    while True:
        if not user_msg:
            try:
                user_msg = typer.prompt("you", default="", show_default=False)
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]entity-approve ended.[/dim]")
                return

        if not user_msg.strip() or user_msg.strip().lower() in _EXIT_WORDS:
            console.print("[dim]entity-approve ended.[/dim]")
            return

        try:
            result = asyncio.run(
                run_skill(
                    skill="entity-approve",
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
            console.print("\n[dim]entity-approve interrupted.[/dim]")
            return

        reply = (result.get("text") or "").strip()
        if reply:
            console.print(f"\n[bold cyan]conch[/bold cyan]\n{reply}\n")
        else:
            console.print(
                "[dim](no visible reply — skill may have ended silently)[/dim]"
            )

        # Auto-exit when the skill itself signals an empty inbox so the
        # REPL doesn't hang asking the user for input it can't act on.
        if _looks_empty_inbox(reply):
            return

        # Heuristic: first-turn skill response with explicit "종료." also
        # closes — covers cancel paths the user already drove.
        if first_turn and "종료" in reply and "처리" not in reply:
            return
        first_turn = False

        user_msg = None


def _run_sync_phase(date: str | None) -> None:
    session = sync_session_name(date)
    opener = date if date else "today"

    console.print()
    console.print("[bold]━━━ Capture → KR Sync ━━━[/bold]")
    console.print(f"[dim]sync session:[/dim] [cyan]{session}[/cyan]")
    console.print(
        "[dim]review proposed kr links; approve subset, all (y/yes), or cancel.[/dim]\n"
    )

    user_msg: str | None = opener
    while True:
        if not user_msg:
            try:
                user_msg = typer.prompt("you", default="", show_default=False)
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]sync ended.[/dim]")
                return

        if not user_msg.strip() or user_msg.strip().lower() in _EXIT_WORDS:
            console.print("[dim]sync ended.[/dim]")
            return

        try:
            result = asyncio.run(
                run_skill(
                    skill="capture-progress-sync",
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
            console.print("\n[dim]sync interrupted.[/dim]")
            return

        reply = (result.get("text") or "").strip()
        if reply:
            console.print(f"\n[bold cyan]conch[/bold cyan]\n{reply}\n")
        else:
            console.print(
                "[dim](no visible reply — skill may have ended silently)[/dim]"
            )

        user_msg = None


def retro_cmd(
    date: str | None = typer.Argument(
        None, help="KST date (YYYY-MM-DD). Default: today.",
    ),
    skip_entity_approve: bool = typer.Option(
        False, "--skip-entity-approve",
        help="Skip the FR-C2 entity drafts inbox.",
    ),
    skip_sync: bool = typer.Option(
        False, "--skip-sync",
        help="Skip the capture-KR sync REPL.",
    ),
    raw: bool = typer.Option(
        False, "--raw",
        help="Print the retro as raw markdown (no rich rendering).",
    ),
) -> None:
    """Run evening retro → entity drafts inbox → capture-KR sync."""
    _run_retro_phase(date, raw)
    if not skip_entity_approve:
        _run_entity_approve_phase(date)
    if not skip_sync:
        _run_sync_phase(date)
