"""`mcs skill` — manage skill-promotion drafts (FR-E5).

Subcommands:
- propose: stage a draft manually (single-shot)
- list:    show pending drafts (subset of `mcs inbox list`)
- scan:    auto-detect recurring patterns in brain/ via ANN cluster
           → LLM label → draft (FR-E5 v0 detector)

Drafts surface in `mcs inbox list` and the inbox-approve skill
alongside entity drafts, so evening retro is the single review surface.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import typer
from rich.console import Console
from rich.table import Table

from mcs.adapters import skill_corpus, skill_detector, skill_labeler
from mcs.adapters import skill_suggestion as ss
from mcs.adapters.daemon_client import DaemonUnreachable, call_tool


app = typer.Typer(name="skill", help="Skill-promotion drafts (FR-E5).")
console = Console()


def _run(coro):
    try:
        return asyncio.run(coro)
    except DaemonUnreachable as e:
        console.print(f"[red]✗[/red] {e}")
        console.print("  [dim]tip: add --direct to bypass the daemon.[/dim]")
        raise typer.Exit(code=3) from e


@app.command("propose")
def propose_cmd(
    slug: str = typer.Argument(..., help="Slug for the new skill (kebab-case)."),
    name: str | None = typer.Option(
        None, "-n", "--name",
        help="Display name. Defaults to a Title Case form of `slug`.",
    ),
    summary: str | None = typer.Option(
        None, "-s", "--summary",
        help="One-line note explaining what pattern this skill captures.",
    ),
    body_file: Path | None = typer.Option(
        None, "--body",
        help="Path to a .md file whose content becomes the draft body.",
    ),
    session_id: str | None = typer.Option(
        None, "--from-session",
        help="Source Hermes session id, if known (annotation only).",
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Stage a skill-promotion draft for review in the next evening retro."""
    display_name = name or slug.replace("-", " ").title()
    body = ""
    if body_file is not None:
        if not body_file.exists():
            console.print(f"[red]✗[/red] body file not found: {body_file}")
            raise typer.Exit(code=2)
        body = body_file.read_text(encoding="utf-8")

    try:
        sug = ss.create_draft(
            slug=slug,
            name=display_name,
            body=body,
            source_session_id=session_id,
            summary=summary or "",
        )
    except (ValueError, ss.SkillSuggestionError) as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=4) from e

    if as_json:
        typer.echo(json.dumps(sug.to_dict(), ensure_ascii=False, indent=2))
        return

    console.print(
        f"[green]✓[/green] proposed → [cyan]{sug.slug}[/cyan] "
        f"[dim]({sug.path})[/dim]"
    )
    console.print(
        "  [dim]review during next evening retro or via "
        "`mcs inbox approve skill-promotion/" + sug.slug + "`.[/dim]"
    )


@app.command("list")
def list_cmd(
    as_json: bool = typer.Option(False, "--json"),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """Show pending skill-promotion drafts only (subset of `mcs inbox list`)."""
    async def _fetch() -> list[dict[str, Any]]:
        if direct:
            return [s.to_dict() for s in ss.list_drafts()]
        return await call_tool(
            "memory.inbox_list", {"item_type": "skill-promotion"}
        )

    data = _run(_fetch())
    if as_json:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if not data:
        console.print("[dim]no pending skill suggestions.[/dim]")
        return
    for entry in data:
        # Normalise both the direct (SkillSuggestion.to_dict) and the
        # daemon (InboxItem.to_dict) shapes — the latter has an `id`/`summary`
        # pair instead of slug/name.
        slug = entry.get("slug") or entry.get("id") or "?"
        name = entry.get("name") or entry.get("summary") or ""
        console.print(f"[cyan]{slug}[/cyan]  {name}")


# ─── scan (FR-E5 detector) ─────────────────────────────────────────────

_KST = ZoneInfo("Asia/Seoul")


def _format_candidate_row(c: skill_detector.SkillCandidate) -> tuple[str, ...]:
    domains = ",".join(c.payload.get("domains") or []) or "—"
    seed = c.seed_id.split(":", 1)[-1]
    return (
        seed[:48],
        str(len(c.member_ids)),
        f"{c.time_spread_days:.1f}d",
        f"{c.avg_score:.2f}",
        domains,
    )


@app.command("scan")
def scan_cmd(
    days: int = typer.Option(
        30, "-d", "--days",
        help="Lookback window in days for the corpus.",
    ),
    min_cluster: int = typer.Option(
        4, "--min-cluster",
        help="Minimum cluster size to consider (default: 4).",
    ),
    similarity: float = typer.Option(
        0.020, "--similarity",
        help=(
            "Minimum RRF-fusion score for an ANN edge. memsearch hybrid "
            "search caps at ~0.033 (top-1) and falls to ~0.016 "
            "(unrelated). Default 0.020 keeps the strongest neighbours."
        ),
    ),
    min_spread: float = typer.Option(
        2.0, "--min-spread",
        help="Minimum time spread (days) so single-day bursts don't qualify.",
    ),
    min_avg_score: float = typer.Option(
        0.020, "--min-avg-score",
        help="Minimum average RRF score inside a cluster (see --similarity).",
    ),
    source: list[str] = typer.Option(
        [], "--source",
        help="Restrict corpus to specific source types (default: all registered).",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Print candidates only — skip LLM labelling and draft creation.",
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Detect recurring patterns in brain/ and stage skill-promotion drafts.

    The detector queries memsearch for each capture's nearest neighbours,
    runs union-find over similarity edges, and gates clusters by size
    + time spread + average score. Each surviving cluster is labelled
    by the Hermes `skill-name-suggest` skill, which returns either a
    JSON draft (slug/name/summary/body) or `slug: null` to decline.

    --dry-run skips the LLM and draft creation; useful for tuning
    --similarity / --min-cluster against your current corpus before
    incurring labelling cost.
    """
    if not 0.0 <= similarity <= 1.0:
        raise typer.BadParameter("--similarity must be in [0, 1]")

    since = datetime.now(_KST) - timedelta(days=days)
    source_types = source or None

    # 1) Build the corpus.
    corpus = skill_corpus.list_corpus(since=since, source_types=source_types)
    console.print(
        f"[dim]corpus:[/dim] {len(corpus)} items "
        f"[dim](since {since.date()}, sources={source_types or 'all'})[/dim]"
    )
    if not corpus:
        console.print("[dim]no corpus items in window.[/dim]")
        return

    # 2) Detect candidate clusters via ANN.
    candidates = asyncio.run(
        skill_detector.find_candidates(
            corpus,
            similarity_threshold=similarity,
            min_cluster_size=min_cluster,
            min_time_spread_days=min_spread,
            min_avg_score=min_avg_score,
        )
    )

    if as_json and dry_run:
        typer.echo(json.dumps(
            [c.to_dict() for c in candidates], ensure_ascii=False, indent=2
        ))
        return

    if not candidates:
        console.print("[dim]no candidates met the gates.[/dim]")
        return

    # 3) Render candidates table.
    t = Table(title=f"Candidates · {len(candidates)}", show_header=True, header_style="bold")
    t.add_column("seed", style="cyan")
    t.add_column("size", justify="right")
    t.add_column("spread")
    t.add_column("avg", justify="right")
    t.add_column("domains", style="dim")
    for c in candidates:
        t.add_row(*_format_candidate_row(c))
    console.print(t)

    if dry_run:
        console.print("[dim]--dry-run: skipping LLM labelling.[/dim]")
        return

    # 4) Label + persist drafts.
    console.print(
        f"[dim]labelling {len(candidates)} candidate(s) via Hermes "
        f"`skill-name-suggest` …[/dim]"
    )
    labels = asyncio.run(skill_labeler.label_candidates(candidates))

    if as_json:
        typer.echo(json.dumps(
            [l.to_dict() for l in labels], ensure_ascii=False, indent=2
        ))
        return

    summary = {"created": 0, "skipped-by-llm": 0, "skipped-existing": 0, "error": 0}
    for label in labels:
        summary[label.status] = summary.get(label.status, 0) + 1
        if label.status == "created":
            console.print(
                f"[green]✓[/green] {label.slug} "
                f"[dim]({label.draft_path})[/dim]"
            )
        elif label.status == "skipped-by-llm":
            console.print(
                f"[dim]⊘ {label.candidate_seed_id} "
                f"— {label.reason}[/dim]"
            )
        elif label.status == "skipped-existing":
            console.print(
                f"[yellow]→[/yellow] {label.slug} already exists "
                f"[dim]({label.reason})[/dim]"
            )
        else:
            console.print(
                f"[red]✗[/red] {label.candidate_seed_id} "
                f"— {label.reason}"
            )

    console.print(
        f"[dim]done: {summary['created']} created, "
        f"{summary['skipped-by-llm']} declined, "
        f"{summary['skipped-existing']} duplicates, "
        f"{summary['error']} errors.[/dim]"
    )
