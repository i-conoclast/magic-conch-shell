"""`mcs okr` — mechanical CRUD over brain/objectives/.

Six subcommands:
  list              Active + achieved Objectives (filters: quarter, domain, status)
  show <id>         One Objective with KR detail
  update <kr-id>    Patch a KR's fields
  close <obj-id>    Set Objective status (achieved / abandoned / paused)
  kr-add <obj-id>   Append a new KR (non-interactive)
  kr-list           Flat KR listing (filters: objective, status, --due-before)

All commands support `--direct` to bypass the daemon for debugging or
offline use; read commands also support `--json` for machine output.

Dialogue-driven creation (interactive OKR intake) lives in `mcs okr new`,
which routes through Hermes and is implemented separately.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from mcs.adapters.daemon_client import DaemonUnreachable, call_tool
from mcs.adapters.hermes_client import (
    HermesAuthError,
    HermesError,
    HermesUnreachable,
    intake_session_name,
    run_skill,
    update_session_name,
)
from mcs.adapters.memory import DOMAINS
from mcs.adapters.okr import (
    OKRError,
    OKRNotFound,
    create_kr as core_create_kr,
    get as core_get,
    list_active as core_list_active,
    update_kr as core_update_kr,
    update_objective as core_update_objective,
)

app = typer.Typer(name="okr", help="Manage OKRs under brain/objectives/.")
console = Console()


# ─── Status symbols ─────────────────────────────────────────────────────

_KR_SYMBOL = {
    "pending": "○",
    "in_progress": "◐",
    "achieved": "✓",
    "missed": "✗",
}
_KR_UNACHIEVED = frozenset({"pending", "in_progress"})


def _kr_symbol(status: str) -> str:
    return _KR_SYMBOL.get(status, "·")


def _kst_today() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")


# ─── Dispatch helpers (direct vs daemon) ───────────────────────────────

async def _fetch_list(
    quarter: str | None, statuses: list[str] | None, domain: str | None, direct: bool
) -> list[dict[str, Any]]:
    if direct:
        return [
            o.to_dict()
            for o in core_list_active(quarter, statuses=statuses, domain=domain)
        ]
    return await call_tool(
        "okr.list_active",
        {"quarter": quarter, "statuses": statuses, "domain": domain},
    )


async def _fetch_get(obj_id: str, direct: bool) -> dict[str, Any]:
    if direct:
        try:
            return core_get(obj_id).to_dict()
        except OKRNotFound as e:
            return {"error": str(e)}
    data = await call_tool("okr.get", {"objective_id": obj_id})
    return data


async def _do_update_kr(kr_id: str, fields: dict[str, Any], direct: bool) -> dict[str, Any]:
    if direct:
        try:
            return core_update_kr(kr_id, **fields).to_dict()
        except (OKRError, OKRNotFound) as e:
            return {"error": str(e)}
    return await call_tool("okr.update_kr", {"kr_id": kr_id, "fields": fields})


async def _do_update_objective(
    obj_id: str, fields: dict[str, Any], direct: bool
) -> dict[str, Any]:
    if direct:
        try:
            return core_update_objective(obj_id, **fields).to_dict()
        except (OKRError, OKRNotFound) as e:
            return {"error": str(e)}
    return await call_tool(
        "okr.update_objective", {"objective_id": obj_id, "fields": fields}
    )


async def _do_create_kr(
    obj_id: str, payload: dict[str, Any], direct: bool
) -> dict[str, Any]:
    if direct:
        try:
            kr = core_create_kr(obj_id, **payload)
            return kr.to_dict()
        except (OKRError, OKRNotFound) as e:
            return {"error": str(e)}
    return await call_tool("okr.create_kr", {"parent_id": obj_id, **payload})


def _run(coro):
    """Wrap the asyncio.run + DaemonUnreachable → Typer.Exit(3) pattern."""
    try:
        return asyncio.run(coro)
    except DaemonUnreachable as e:
        console.print(f"[red]✗[/red] {e}")
        console.print(
            "  [dim]tip: add --direct to bypass the daemon.[/dim]"
        )
        raise typer.Exit(code=3) from e


# ─── list ───────────────────────────────────────────────────────────────

@app.command("list")
def list_cmd(
    quarter: str | None = typer.Option(None, "-q", "--quarter", help="e.g. 2026-Q2"),
    domain: str | None = typer.Option(
        None, "-d", "--domain", help=f"One of {sorted(DOMAINS)}."
    ),
    status: str | None = typer.Option(
        None,
        "-s",
        "--status",
        help="active | paused | achieved | abandoned | all (default: active+achieved)",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON."),
    direct: bool = typer.Option(False, "--direct", help="Bypass the daemon."),
) -> None:
    """List active + achieved Objectives (filters: quarter, domain, status)."""
    statuses = [status] if status else None
    if status == "all":
        statuses = ["all"]

    data = _run(_fetch_list(quarter, statuses, domain, direct))

    if as_json:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if not data:
        console.print("[dim]no matching OKRs.[/dim]")
        return

    title = "OKRs"
    if quarter:
        title += f" · {quarter}"
    if domain:
        title += f" · {domain}"
    if status:
        title += f" · status={status}"

    t = Table(title=title, show_header=True, header_style="bold")
    t.add_column("id", style="cyan")
    t.add_column("domain", style="dim")
    t.add_column("krs", justify="right")
    t.add_column("status")
    t.add_column("conf", justify="right")

    for obj in data:
        krs = obj.get("krs") or []
        achieved = sum(1 for k in krs if k.get("status") == "achieved")
        t.add_row(
            obj["id"],
            obj.get("domain") or "—",
            f"{achieved}/{len(krs)}",
            obj["status"],
            f"{float(obj.get('confidence') or 0):.2f}",
        )
    console.print(t)


# ─── show ───────────────────────────────────────────────────────────────

@app.command("show")
def show_cmd(
    objective_id: str = typer.Argument(..., help="e.g. 2026-Q2-career-mle-role"),
    as_json: bool = typer.Option(False, "--json"),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """Show one Objective with its KRs."""
    data = _run(_fetch_get(objective_id, direct))
    if "error" in data:
        console.print(f"[red]✗[/red] {data['error']}")
        raise typer.Exit(code=4)

    if as_json:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return

    header_lines = [
        f"[bold cyan]{data['id']}[/bold cyan]",
        (
            f"{data.get('domain') or '—'} · {data['status']}"
            f" · confidence {float(data.get('confidence') or 0):.2f}"
        ),
        f"[dim]updated:[/dim] {data.get('updated_at') or '—'}",
    ]
    entities = data.get("entities") or []
    if entities:
        header_lines.append(f"[dim]entities:[/dim] {', '.join(entities)}")
    console.print(Panel("\n".join(header_lines), border_style="dim"))

    body = (data.get("body") or "").strip()
    if body:
        console.print(Markdown(body))
        console.print()

    krs = data.get("krs") or []
    if not krs:
        console.print("[dim](no KRs)[/dim]")
        return

    t = Table(show_header=True, header_style="bold", title="KRs")
    t.add_column("", width=1)
    t.add_column("id", style="cyan")
    t.add_column("text")
    t.add_column("status")
    t.add_column("progress", justify="right")
    t.add_column("due", style="dim")
    for kr in krs:
        target = float(kr.get("target") or 0)
        current = float(kr.get("current") or 0)
        t.add_row(
            _kr_symbol(kr.get("status", "")),
            kr["id"].rsplit(".", 1)[-1],  # show kr-1 instead of full
            kr.get("text") or "",
            kr.get("status") or "",
            f"{current:g}/{target:g}",
            kr.get("due") or "—",
        )
    console.print(t)


# ─── update (KR fields) ────────────────────────────────────────────────

@app.command("update")
def update_cmd(
    id: str = typer.Argument(
        ...,
        help=(
            "KR id (e.g. 2026-Q2-career-mle-role.kr-2) for mechanical patch, "
            "or Objective id + --interactive for Hermes-driven review."
        ),
    ),
    text: str | None = typer.Option(None, "--text"),
    target: float | None = typer.Option(None, "--target"),
    current: float | None = typer.Option(None, "--current"),
    unit: str | None = typer.Option(None, "--unit"),
    status: str | None = typer.Option(None, "--status"),
    due: str | None = typer.Option(None, "--due", help="ISO date, e.g. 2026-06-30"),
    interactive: bool = typer.Option(
        False,
        "-i",
        "--interactive",
        help="Route to Hermes okr-update skill (dialogue). Id must be an Objective id.",
    ),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """Patch KR fields (mechanical) or run an interactive OKR review."""
    if interactive:
        if ".kr-" in id:
            console.print(
                "[red]✗[/red] --interactive expects an Objective id, not a KR id."
            )
            raise typer.Exit(code=2)
        session = update_session_name(id)
        _run_agent_repl(
            "okr-update",
            session=session,
            opener=id,            # skill reads the Objective id from opener
            greeting_hint=f"reviewing {id}",
        )
        return

    # Mechanical path requires a KR id.
    if ".kr-" not in id:
        console.print(
            "[red]✗[/red] mechanical update needs a KR id "
            "(use -i/--interactive for Objective-level review)."
        )
        raise typer.Exit(code=2)
    kr_id = id

    # Fetch before for diff
    parent = kr_id.rsplit(".kr-", 1)[0]
    before_obj = _run(_fetch_get(parent, direct))
    if "error" in before_obj:
        console.print(f"[red]✗[/red] {before_obj['error']}")
        raise typer.Exit(code=4)
    before_kr = next(
        (k for k in before_obj.get("krs") or [] if k.get("id") == kr_id), None
    )
    if before_kr is None:
        console.print(f"[red]✗[/red] kr {kr_id!r} not found in {parent}")
        raise typer.Exit(code=4)

    fields: dict[str, Any] = {}
    for k, v in (
        ("text", text), ("target", target), ("current", current),
        ("unit", unit), ("status", status), ("due", due),
    ):
        if v is not None:
            fields[k] = v

    if not fields:
        console.print("[yellow]no fields to update.[/yellow] try --status, --current, ...")
        raise typer.Exit(code=2)

    out = _run(_do_update_kr(kr_id, fields, direct))
    if "error" in out:
        console.print(f"[red]✗[/red] {out['error']}")
        raise typer.Exit(code=2)

    console.print(f"[green]✓[/green] [cyan]{kr_id}[/cyan]")
    for k in fields:
        old = before_kr.get(k)
        new = out.get(k)
        if old != new:
            console.print(f"  [dim]{k:<8}[/dim] {old}  [dim]→[/dim]  {new}")
    console.print(f"  [dim]updated_at re-stamped[/dim]")


# ─── close (Objective status change) ───────────────────────────────────

@app.command("close")
def close_cmd(
    objective_id: str = typer.Argument(...),
    status: str = typer.Option(
        "achieved", "--status",
        help="achieved | abandoned | paused (default achieved)",
    ),
    note: str | None = typer.Option(
        None, "--note",
        help="Append a timestamped note to the objective body.",
    ),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """Close an Objective (default status=achieved). Optionally append a note."""
    obj = _run(_fetch_get(objective_id, direct))
    if "error" in obj:
        console.print(f"[red]✗[/red] {obj['error']}")
        raise typer.Exit(code=4)

    old_status = obj["status"]
    fields: dict[str, Any] = {"status": status}
    if note:
        stamp = _kst_today()
        new_body = (obj.get("body") or "").rstrip()
        new_body += f"\n\n---\n\n**{stamp} closed** ({status}): {note}\n"
        fields["body"] = new_body

    out = _run(_do_update_objective(objective_id, fields, direct))
    if "error" in out:
        console.print(f"[red]✗[/red] {out['error']}")
        raise typer.Exit(code=2)

    console.print(f"[green]✓[/green] [cyan]{objective_id}[/cyan]")
    console.print(f"  [dim]status:[/dim] {old_status}  [dim]→[/dim]  {out['status']}")
    if note:
        console.print(f"  [dim]note appended:[/dim] {note[:80]}")


# ─── kr-add ─────────────────────────────────────────────────────────────

@app.command("kr-add")
def kr_add_cmd(
    objective_id: str = typer.Argument(...),
    text: str = typer.Option(..., "--text", help="KR description (required)."),
    target: float = typer.Option(1.0, "--target"),
    current: float = typer.Option(0.0, "--current"),
    unit: str = typer.Option("count", "--unit", help="count|percent|currency|binary"),
    status: str = typer.Option("pending", "--status"),
    due: str | None = typer.Option(None, "--due"),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """Append a new KR to an existing Objective."""
    payload: dict[str, Any] = {
        "text": text,
        "target": target,
        "current": current,
        "unit": unit,
        "status": status,
        "due": due,
    }
    out = _run(_do_create_kr(objective_id, payload, direct))
    if "error" in out:
        console.print(f"[red]✗[/red] {out['error']}")
        raise typer.Exit(code=2)

    console.print(f"[green]✓[/green] [cyan]{out['id']}[/cyan]")
    console.print(f"  [dim]text   :[/dim] {out['text']}")
    console.print(
        f"  [dim]target :[/dim] {out['target']:g} · "
        f"[dim]unit:[/dim] {out['unit']}"
    )
    console.print(f"  [dim]status :[/dim] {out['status']}")
    if out.get("due"):
        console.print(f"  [dim]due    :[/dim] {out['due']}")


# ─── agent REPL (shared by `new` + `update --interactive`) ────────────

_EXIT_WORDS = frozenset({"quit", "exit", "q", "그만", "나갈게", "끝"})


def _run_agent_repl(
    skill: str,
    *,
    session: str,
    opener: str | None,
    greeting_hint: str | None = None,
) -> None:
    """Drive a multi-turn conversation with a Hermes skill.

    The loop blocks on user input, posts each message to
    `/v1/responses` with a fixed `conversation` name, and prints the
    assistant's reply. Empty input, Ctrl-C, or an exit word terminates
    the loop; whatever was already persisted by the skill stays.
    """
    console.print(f"[dim]session:[/dim] [cyan]{session}[/cyan]")
    if greeting_hint:
        console.print(f"[dim]{greeting_hint}[/dim]")
    console.print(
        "[dim]empty line or 'quit' to end · the skill saves as it goes.[/dim]\n"
    )

    user_msg = opener

    while True:
        if not user_msg:
            try:
                user_msg = typer.prompt("you", default="", show_default=False)
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]ended.[/dim]")
                return

        if not user_msg.strip() or user_msg.strip().lower() in _EXIT_WORDS:
            console.print("[dim]ended.[/dim]")
            return

        try:
            result = asyncio.run(
                run_skill(skill=skill, opener=user_msg, conversation=session)
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
            console.print("\n[dim]interrupted — partial state saved.[/dim]")
            return

        reply = (result.get("text") or "").strip()
        if reply:
            console.print(f"\n[bold cyan]conch[/bold cyan]\n{reply}\n")
        else:
            console.print("[dim](no visible reply — skill may have ended silently)[/dim]")

        user_msg = None  # next iteration prompts


# ─── new (agent — okr-intake skill) ────────────────────────────────────

@app.command("new")
def new_cmd(
    opener: str | None = typer.Argument(
        None,
        help="Opening message to start the intake, e.g. '커리어 OKR 하나 세우자'.",
    ),
    resume: str | None = typer.Option(
        None,
        "--resume",
        help="Continue an existing intake session by name.",
    ),
) -> None:
    """Start a new OKR intake conversation (agent-driven via Hermes)."""
    if resume:
        session = resume
        hint = f"resuming · type to continue"
    else:
        session = intake_session_name()
        hint = "new intake session"
    _run_agent_repl(
        "okr-intake",
        session=session,
        opener=opener,
        greeting_hint=hint,
    )


# ─── kr-list ────────────────────────────────────────────────────────────

@app.command("kr-list")
def kr_list_cmd(
    objective_id: str | None = typer.Option(
        None, "-o", "--objective",
        help="Restrict to a single Objective.",
    ),
    status: str | None = typer.Option(
        None, "-s", "--status",
        help="pending | in_progress | achieved | missed | all (default: unachieved)",
    ),
    due_before: str | None = typer.Option(
        None, "--due-before", help="ISO date; KRs with due ≤ this only."
    ),
    as_json: bool = typer.Option(False, "--json"),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """List KRs across Objectives. Defaults to unachieved (pending + in_progress)."""
    # Fetch: either single Objective or all
    if objective_id:
        obj = _run(_fetch_get(objective_id, direct))
        if "error" in obj:
            console.print(f"[red]✗[/red] {obj['error']}")
            raise typer.Exit(code=4)
        krs: list[dict[str, Any]] = list(obj.get("krs") or [])
    else:
        objs = _run(_fetch_list(None, ["all"], None, direct))
        krs = []
        for o in objs:
            krs.extend(o.get("krs") or [])

    # Filter by status
    if status == "all":
        pass
    elif status:
        krs = [k for k in krs if k.get("status") == status]
    else:
        krs = [k for k in krs if k.get("status") in _KR_UNACHIEVED]

    # Filter by due date (ISO string compare works for YYYY-MM-DD)
    if due_before:
        krs = [k for k in krs if (k.get("due") or "") and k["due"] <= due_before]

    krs.sort(key=lambda k: (k.get("due") or "9999", k.get("id") or ""))

    if as_json:
        typer.echo(json.dumps(krs, ensure_ascii=False, indent=2))
        return

    if not krs:
        console.print("[dim]no matching KRs.[/dim]")
        return

    title_bits = []
    if objective_id:
        title_bits.append(objective_id)
    if status and status != "all":
        title_bits.append(f"status={status}")
    elif not status:
        title_bits.append("unachieved")
    if due_before:
        title_bits.append(f"due ≤ {due_before}")
    title = "KRs · " + " · ".join(title_bits) if title_bits else "KRs"

    t = Table(title=title, show_header=True, header_style="bold")
    t.add_column("", width=1)
    t.add_column("id", style="cyan")
    t.add_column("text")
    t.add_column("status")
    t.add_column("progress", justify="right")
    t.add_column("due", style="dim")
    for kr in krs:
        target = float(kr.get("target") or 0)
        current = float(kr.get("current") or 0)
        t.add_row(
            _kr_symbol(kr.get("status", "")),
            kr["id"],
            kr.get("text") or "",
            kr.get("status") or "",
            f"{current:g}/{target:g}",
            kr.get("due") or "—",
        )
    console.print(t)
