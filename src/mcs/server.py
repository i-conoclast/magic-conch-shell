"""magic-conch-shell MCP server — single process that owns brain/ state.

Exposes tools over FastMCP HTTP transport so CLI commands, Hermes Agent,
and the background watcher all share one MemSearch engine instance.
This is the architectural fix for the Milvus Lite single-process lock:
only this process opens `.brain/memsearch.db`.

Tools:
  memory.capture — write one-line memo + incremental index
  memory.search  — hybrid search with domain/type/entity filters
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from mcs.adapters.memory import (
    DOMAINS,
    MemoAmbiguous,
    MemoNotFound,
    add_okr_link as core_add_okr_link,
    add_task_link as core_add_task_link,
    capture as core_capture,
    capture_structured as core_capture_structured,
    daily_file_path as core_daily_file_path,
    list_captures_by_date as core_list_captures_by_date,
    load_memo,
    upsert_daily_section as core_upsert_daily_section,
)
from mcs.adapters import notion as notion_mod
from mcs.adapters.notion import (
    CaptureInput,
    DailyTaskInput,
    NotionConfigError,
    NotionError,
)
from mcs.adapters.okr import (
    OKRError,
    OKRNotFound,
    archive_kr_agent as core_okr_archive_kr_agent,
    create_kr as core_okr_create_kr,
    create_objective as core_okr_create_objective,
    find_kr_agent as core_okr_find_kr_agent,
    get as core_okr_get,
    get_kr as core_okr_get_kr,
    list_active as core_okr_list_active,
    set_kr_notion_page_id,
    set_objective_notion_page_id,
    spawn_kr_agent as core_okr_spawn_kr_agent,
    update_kr as core_okr_update_kr,
    update_objective as core_okr_update_objective,
)
from mcs.adapters.search import search as core_search, sync_file
from mcs.adapters.templates import TemplateError, list_templates, load_template
from mcs.config import load_settings


# Lifespan state — watcher handle so we can stop it cleanly on shutdown.
_watcher_observer: Any = None


@asynccontextmanager
async def _lifespan(_server: FastMCP):
    """Bind the watcher to the running server loop on startup, stop on shutdown."""
    global _watcher_observer
    # Lazy imports avoid a circular dependency at module-load time.
    from mcs.adapters.watcher import bind_main_loop, start_watcher

    bind_main_loop(asyncio.get_running_loop())

    if _watcher_observer is None and _watch_enabled:
        _watcher_observer, _ = start_watcher()
        settings = load_settings()
        print(
            f"[watcher] active on {settings.brain_dir}/signals + /domains",
            flush=True,
        )

    try:
        yield
    finally:
        if _watcher_observer is not None:
            _watcher_observer.stop()
            _watcher_observer.join(timeout=5.0)
            _watcher_observer = None


# Toggle flipped by run_server() before mcp.run() is called.
_watch_enabled: bool = True


mcp = FastMCP(name="mcs", version="0.1.0", lifespan=_lifespan)


@mcp.tool(
    name="memory.capture",
    description="Capture a one-line memo to brain/ and incrementally index it.",
)
async def memory_capture(
    text: str,
    domain: str | None = None,
    entities: list[str] | None = None,
    source: str = "typed",
    title: str | None = None,
    okrs: list[str] | None = None,
    index: bool = True,
    push_notion: bool = True,
) -> dict[str, Any]:
    """Write a memo. Returns {path, id, type, domain, indexed, notion_pushed}."""
    result = core_capture(
        text=text,
        domain=domain,
        entities=entities or [],
        source=source,
        title=title,
        okrs=okrs or [],
    )
    indexed = False
    if index:
        try:
            await sync_file(result.path)
            indexed = True
        except Exception:
            # capture succeeded on disk — indexing is best-effort.
            indexed = False

    notion_pushed = False
    notion_page_id: str | None = None
    if push_notion:
        try:
            # New captures have no task links yet — capture-progress-sync
            # later runs add_task_link + push_capture to wire them up.
            cap_input = CaptureInput(
                mcs_id=result.id,
                text=text,
                type=result.type,
                domain=result.domain,
                created=result.id[:10],   # slug prefix is YYYY-MM-DD
                entities=list(entities or []),
                source=source,
            )
            push_res = await notion_mod.push_capture(cap_input)
            notion_page_id = push_res.notion_page_id
            notion_pushed = True
        except Exception:
            notion_pushed = False

    settings = load_settings()
    try:
        rel = str(result.path.resolve().relative_to(settings.repo_root.resolve()))
    except ValueError:
        rel = str(result.path)

    return {
        "path": str(result.path),
        "rel_path": rel,
        "id": result.id,
        "type": result.type,
        "domain": result.domain,
        "indexed": indexed,
        "notion_pushed": notion_pushed,
        "notion_page_id": notion_page_id,
    }


# ─── OKR tools ──────────────────────────────────────────────────────────

@mcp.tool(
    name="okr.list_active",
    description=(
        "List Objectives (default status ∈ {active, achieved})."
        " Pass statuses=['all'] for every status, or a specific subset."
        " Optional quarter + domain filters."
    ),
)
async def okr_list_active(
    quarter: str | None = None,
    statuses: list[str] | None = None,
    domain: str | None = None,
) -> list[dict[str, Any]]:
    """Returns [{id, quarter, domain, status, confidence, krs: [...]}]."""
    objs = core_okr_list_active(quarter, statuses=statuses, domain=domain)
    return [o.to_dict() for o in objs]


@mcp.tool(
    name="okr.get",
    description="Load one Objective (with its KRs) by id.",
)
async def okr_get(objective_id: str) -> dict[str, Any]:
    try:
        return core_okr_get(objective_id).to_dict()
    except OKRNotFound as e:
        return {"error": str(e)}


@mcp.tool(
    name="okr.get_kr",
    description="Load a single KR by id (e.g. '2026-Q2-career-mle-role.kr-1').",
)
async def okr_get_kr(kr_id: str) -> dict[str, Any]:
    try:
        return core_okr_get_kr(kr_id).to_dict()
    except (OKRNotFound, OKRError) as e:
        return {"error": str(e)}


@mcp.tool(
    name="okr.create_objective",
    description="Create a new Objective folder with _objective.md.",
)
async def okr_create_objective(
    slug: str,
    quarter: str,
    domain: str,
    confidence: float = 0.5,
    entities: list[str] | None = None,
    body: str = "",
) -> dict[str, Any]:
    try:
        obj = core_okr_create_objective(
            slug=slug,
            quarter=quarter,
            domain=domain,
            confidence=confidence,
            entities=entities,
            body=body,
        )
    except OKRError as e:
        return {"error": str(e)}
    return obj.to_dict()


@mcp.tool(
    name="okr.create_kr",
    description="Add a KR to an existing Objective.",
)
async def okr_create_kr(
    parent_id: str,
    text: str,
    target: float = 1.0,
    current: float = 0.0,
    unit: str = "count",
    status: str = "pending",
    due: str | None = None,
    body: str = "",
) -> dict[str, Any]:
    try:
        kr = core_okr_create_kr(
            parent_id,
            text=text,
            target=target,
            current=current,
            unit=unit,
            status=status,
            due=due,
            body=body,
        )
    except (OKRError, OKRNotFound) as e:
        return {"error": str(e)}
    return kr.to_dict()


@mcp.tool(
    name="okr.update_kr",
    description=(
        "Patch KR fields (text/target/current/unit/status/due/body)"
        " and re-stamp updated_at. If the KR has a notion_page_id"
        " (i.e. it was previously pushed to Notion via okr.push), the"
        " mcs_kr_tracker row is also updated best-effort so Notion"
        " stays in sync without a manual re-push."
    ),
)
async def okr_update_kr(kr_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    try:
        kr = core_okr_update_kr(kr_id, **fields)
    except (OKRError, OKRNotFound) as e:
        return {"error": str(e)}

    # Best-effort Notion sync — failures don't undo the brain/ write.
    if kr.notion_page_id:
        try:
            obj = core_okr_get(kr.parent)
            await notion_mod.push_kr(
                mcs_id=kr.id,
                name=kr.text,
                objective_notion_id=obj.notion_page_id,
                target=kr.target,
                current=kr.current,
                unit=kr.unit,
                status=kr.status,
                due=kr.due,
                quarter=obj.quarter,
                existing_page_id=kr.notion_page_id,
            )
        except Exception:
            pass
    return kr.to_dict()


@mcp.tool(
    name="okr.update_objective",
    description=(
        "Patch Objective-level fields (status/confidence/domain/entities/body)."
        " Auto-syncs to Notion mcs_okr_master if notion_page_id is set."
    ),
)
async def okr_update_objective(
    objective_id: str, fields: dict[str, Any]
) -> dict[str, Any]:
    try:
        obj = core_okr_update_objective(objective_id, **fields)
    except (OKRError, OKRNotFound) as e:
        return {"error": str(e)}

    if obj.notion_page_id:
        try:
            obj_name = obj.body.split("\n", 1)[0].strip("# ").strip() or obj.id
            await notion_mod.push_objective(
                mcs_id=obj.id,
                name=obj_name,
                quarter=obj.quarter,
                domain=obj.domain,
                status=obj.status,
                confidence=obj.confidence,
                existing_page_id=obj.notion_page_id,
            )
        except Exception:
            pass

        # Cascade picks up KR status updates — re-sync those too if pushed.
        for kr in obj.krs:
            if kr.notion_page_id:
                try:
                    await notion_mod.push_kr(
                        mcs_id=kr.id,
                        name=kr.text,
                        objective_notion_id=obj.notion_page_id,
                        target=kr.target,
                        current=kr.current,
                        unit=kr.unit,
                        status=kr.status,
                        due=kr.due,
                        quarter=obj.quarter,
                        existing_page_id=kr.notion_page_id,
                    )
                except Exception:
                    pass
    return obj.to_dict()


@mcp.tool(
    name="okr.spawn_kr_agent",
    description=(
        "Create a per-KR Hermes skill at skills/objectives/<dashed-kr-id>/SKILL.md."
        " Populates goal/parent context/acceptance criteria from the KR + Objective."
        " Returns {path, slug, created} or {error}."
    ),
)
async def okr_spawn_kr_agent(
    kr_id: str,
    acceptance_criteria: list[str] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    try:
        path = core_okr_spawn_kr_agent(
            kr_id,
            acceptance_criteria=acceptance_criteria,
            overwrite=overwrite,
        )
    except (OKRError, OKRNotFound) as e:
        return {"error": str(e)}
    settings = load_settings()
    try:
        rel = str(path.relative_to(settings.repo_root.resolve()))
    except ValueError:
        rel = str(path)
    return {
        "path": str(path),
        "rel_path": rel,
        "slug": path.parent.name,
        "created": True,
    }


@mcp.tool(
    name="okr.archive_kr_agent",
    description=(
        "Close out a KR's agent folder. action='archive' moves it to"
        " archive/skills/objectives/<slug>-<YYYY-MM-DD>/ (restore via mv);"
        " 'delete' removes it; 'keep' leaves the folder but stamps"
        " metadata.mcs.archived_on so the agent self-describes as closed."
    ),
)
async def okr_archive_kr_agent(
    kr_id: str, action: str = "archive"
) -> dict[str, Any]:
    try:
        result = core_okr_archive_kr_agent(kr_id, action=action)
    except (OKRError, OKRNotFound) as e:
        return {"error": str(e)}
    return result


@mcp.tool(
    name="okr.find_kr_agent",
    description=(
        "Look up the SKILL.md path for a given KR id via metadata.mcs.kr_id."
        " Returns {path, slug} if found, {found: False} otherwise."
    ),
)
async def okr_find_kr_agent(kr_id: str) -> dict[str, Any]:
    path = core_okr_find_kr_agent(kr_id)
    if path is None:
        return {"found": False}
    settings = load_settings()
    try:
        rel = str(path.relative_to(settings.repo_root.resolve()))
    except ValueError:
        rel = str(path)
    return {
        "found": True,
        "path": str(path),
        "rel_path": rel,
        "slug": path.parent.name,
    }


@mcp.tool(
    name="memory.capture_structured",
    description=(
        "Capture a template-based structured record (interview, meeting, experiment)."
        " Fields are coerced per the template schema."
    ),
)
async def memory_capture_structured(
    template: str,
    fields: dict[str, Any] | None = None,
    title: str | None = None,
    source: str = "typed",
    index: bool = True,
) -> dict[str, Any]:
    """Create a structured record. Returns {path, rel_path, id, type, domain, indexed}."""
    try:
        result = core_capture_structured(
            template=template,
            fields=fields or {},
            title=title,
            source=source,
        )
    except TemplateError as e:
        return {"error": str(e)}

    indexed = False
    if index:
        try:
            await sync_file(result.path)
            indexed = True
        except Exception:
            indexed = False

    settings = load_settings()
    try:
        rel = str(result.path.resolve().relative_to(settings.repo_root.resolve()))
    except ValueError:
        rel = str(result.path)

    return {
        "path": str(result.path),
        "rel_path": rel,
        "id": result.id,
        "type": result.type,
        "domain": result.domain,
        "indexed": indexed,
    }


@mcp.tool(
    name="memory.templates_list",
    description="List available structured-capture templates + their field schema.",
)
async def memory_templates_list() -> list[dict[str, Any]]:
    """Return [{name, domain, fields}] for each template in templates/."""
    out: list[dict[str, Any]] = []
    for name in list_templates():
        try:
            t = load_template(name)
        except TemplateError as e:
            out.append({"name": name, "error": str(e)})
            continue
        out.append(
            {
                "name": t.name,
                "domain": t.domain,
                "default_type": t.default_type,
                "fields": [
                    {
                        "name": f.name,
                        "kind": f.kind,
                        "prompt": f.prompt,
                        "required": f.required,
                        "values": f.values,
                        "entity_kind": f.entity_kind,
                    }
                    for f in t.fields
                ],
                "body_sections": t.body_sections,
            }
        )
    return out


@mcp.tool(
    name="memory.upsert_daily_section",
    description=(
        "Write a `## heading` section into brain/daily/YYYY/MM/DD.md. "
        "Creates the file with standard frontmatter if missing; otherwise "
        "replaces the body of an existing section or appends a new one. "
        "Used by morning-brief / evening-retro to persist generated text."
    ),
)
async def memory_upsert_daily_section(
    date: str, heading: str, content: str
) -> dict[str, Any]:
    try:
        path = core_upsert_daily_section(date, heading, content)
    except ValueError as e:
        return {"error": str(e)}
    settings = load_settings()
    try:
        rel = str(path.relative_to(settings.repo_root.resolve()))
    except ValueError:
        rel = str(path)
    return {"path": str(path), "rel_path": rel, "heading": heading, "date": date}


@mcp.tool(
    name="memory.daily_file_path",
    description="Resolve brain/daily/YYYY/MM/DD.md for a given date (existence not checked).",
)
async def memory_daily_file_path(date: str) -> dict[str, Any]:
    try:
        path = core_daily_file_path(date)
    except ValueError as e:
        return {"error": str(e)}
    settings = load_settings()
    try:
        rel = str(path.relative_to(settings.repo_root.resolve()))
    except ValueError:
        rel = str(path)
    return {"path": str(path), "rel_path": rel, "exists": path.exists()}


@mcp.tool(
    name="memory.list_captures",
    description=(
        "List captures (signals + notes) whose frontmatter created_at "
        "falls on a given KST date. Used by capture-progress-sync to "
        "cross-reference the day's memos against active KRs."
    ),
)
async def memory_list_captures(
    date: str,
    domain: str | None = None,
    types: list[str] | None = None,
) -> list[dict[str, Any]]:
    try:
        rows = core_list_captures_by_date(date, domain=domain, types=types)
    except ValueError as e:
        return [{"error": str(e)}]
    return [r.to_dict() for r in rows]


@mcp.tool(
    name="memory.add_okr_link",
    description=(
        "Append kr ids to a capture's frontmatter `okrs:` field. "
        "Idempotent — existing links stay and duplicates are deduped. "
        "Returns the resulting full okrs list or {error}."
    ),
)
async def memory_add_okr_link(
    capture_id: str, kr_ids: list[str]
) -> dict[str, Any]:
    try:
        merged = core_add_okr_link(capture_id, kr_ids)
    except (MemoNotFound, MemoAmbiguous) as e:
        return {"error": str(e)}
    return {"okrs": merged}


@mcp.tool(
    name="memory.add_task_link",
    description=(
        "Append Notion daily_tasks page ids to a capture's frontmatter "
        "`tasks:` field. Idempotent. Used by capture-progress-sync after "
        "the user approves a capture↔task match. Returns the resulting "
        "full tasks list or {error}."
    ),
)
async def memory_add_task_link(
    capture_id: str, task_notion_ids: list[str]
) -> dict[str, Any]:
    try:
        merged = core_add_task_link(capture_id, task_notion_ids)
    except (MemoNotFound, MemoAmbiguous) as e:
        return {"error": str(e)}
    return {"tasks": merged}


@mcp.tool(
    name="notion.list_daily_tasks",
    description=(
        "Query mcs_daily_tasks for rows whose 일시 equals the given KST "
        "date. Returns a list of {page_id, task, status, kr_notion_id, "
        "capture_count, priority, quantity}. capture-progress-sync uses "
        "this as Phase 1 context."
    ),
)
async def notion_list_daily_tasks(date: str) -> list[dict[str, Any]]:
    try:
        rows = await notion_mod.list_daily_tasks(date)
    except (NotionError, NotionConfigError) as e:
        return [{"error": str(e)}]
    return [
        {
            "page_id": r.page_id,
            "task": r.task,
            "status": r.status,
            "kr_notion_id": r.kr_notion_id,
            "capture_count": r.capture_count,
            "priority": r.priority,
            "quantity": r.quantity,
        }
        for r in rows
    ]


@mcp.tool(
    name="notion.update_daily_task_status",
    description=(
        "Set a daily_tasks row's Status. `status` must match an option "
        "name on the DB (e.g. '시작 전' / '진행 중' / '완료')."
    ),
)
async def notion_update_daily_task_status(
    page_id: str, status: str
) -> dict[str, Any]:
    try:
        pid = await notion_mod.update_daily_task_status(page_id, status)
    except (NotionError, NotionConfigError) as e:
        return {"error": str(e)}
    return {"page_id": pid, "status": status}


@mcp.tool(
    name="memory.show",
    description="Read a brain/ memo by id or relative path. Returns frontmatter + body.",
)
async def memory_show(query: str) -> dict[str, Any]:
    """Locate and return a memo.

    `query` can be:
      - Bare slug ('2026-04-22-foo')
      - Relative path under brain/ ('signals/2026-04-22-foo' or '.md' optional)

    Returns {found, id, type, domain, entities, created_at, source, rel_path, body}
    or {found: False, reason, candidates?} if ambiguous / missing.
    """
    try:
        memo = load_memo(query)
    except MemoNotFound as e:
        return {"found": False, "reason": str(e), "candidates": []}
    except MemoAmbiguous as e:
        return {
            "found": False,
            "reason": str(e),
            "candidates": [str(p) for p in e.candidates],
        }
    return {
        "found": True,
        "id": memo.id,
        "type": memo.type,
        "domain": memo.domain,
        "entities": memo.entities,
        "created_at": memo.created_at,
        "source": memo.source,
        "rel_path": memo.rel_path,
        "path": str(memo.path),
        "body": memo.body,
    }


@mcp.tool(
    name="memory.search",
    description=(
        "Hybrid vector + keyword search over brain/. Filters: "
        f"domain={sorted(DOMAINS)}, type=signal|note|daily|entity|objective|kr, "
        "entity=slug. Domain/type are applied via frontmatter so Objectives "
        "and KRs tagged with a domain surface on `-d <domain>` queries."
    ),
)
async def memory_search(
    query: str,
    domain: str | None = None,
    type: str | None = None,
    entity: str | None = None,
    limit: int = 10,
    auto_index: bool = True,
) -> list[dict[str, Any]]:
    """Search. Returns list of hit dicts (score, path, rel_path, snippet, ...)."""
    hits = await core_search(
        query=query,
        domain=domain,
        type=type,
        entity=entity,
        limit=limit,
        auto_index=auto_index,
    )
    return [h.to_dict() for h in hits]


# ─── Notion tools ──────────────────────────────────────────────────────

@mcp.tool(
    name="notion.push_objective",
    description=(
        "Upsert an Objective to mcs_okr_master. Writes notion_page_id back"
        " into brain/objectives/<slug>/_objective.md. Returns"
        " {notion_page_id} or {error}."
    ),
)
async def notion_push_objective(objective_id: str) -> dict[str, Any]:
    try:
        obj = core_okr_get(objective_id)
    except OKRNotFound as e:
        return {"error": str(e)}
    try:
        result = await notion_mod.push_objective(
            mcs_id=obj.id,
            name=obj.body.split("\n", 1)[0].strip("# ").strip() or obj.id,
            quarter=obj.quarter,
            domain=obj.domain,
            status=obj.status,
            confidence=obj.confidence,
            existing_page_id=obj.notion_page_id,
        )
    except (NotionError, NotionConfigError) as e:
        return {"error": str(e)}
    set_objective_notion_page_id(obj.id, result.notion_page_id)
    return {"notion_page_id": result.notion_page_id}


@mcp.tool(
    name="notion.push_kr",
    description=(
        "Upsert a KR to mcs_kr_tracker. Parent Objective must have a"
        " notion_page_id already (run notion.push_objective or okr.push first)."
    ),
)
async def notion_push_kr(kr_id: str) -> dict[str, Any]:
    try:
        kr = core_okr_get_kr(kr_id)
    except (OKRError, OKRNotFound) as e:
        return {"error": str(e)}
    try:
        obj = core_okr_get(kr.parent)
    except OKRNotFound as e:
        return {"error": str(e)}
    try:
        result = await notion_mod.push_kr(
            mcs_id=kr.id,
            name=kr.text,
            objective_notion_id=obj.notion_page_id,
            target=kr.target,
            current=kr.current,
            unit=kr.unit,
            status=kr.status,
            due=kr.due,
            quarter=obj.quarter,
            existing_page_id=kr.notion_page_id,
        )
    except (NotionError, NotionConfigError) as e:
        return {"error": str(e)}
    set_kr_notion_page_id(kr.id, result.notion_page_id)
    return {"notion_page_id": result.notion_page_id}


@mcp.tool(
    name="okr.push",
    description=(
        "Push an Objective plus every KR under it to Notion in one call."
        " Idempotent: existing pages are updated, missing ones created."
    ),
)
async def okr_push(objective_id: str) -> dict[str, Any]:
    try:
        obj = core_okr_get(objective_id)
    except OKRNotFound as e:
        return {"error": str(e)}
    try:
        obj_name = obj.body.split("\n", 1)[0].strip("# ").strip() or obj.id
        obj_res = await notion_mod.push_objective(
            mcs_id=obj.id,
            name=obj_name,
            quarter=obj.quarter,
            domain=obj.domain,
            status=obj.status,
            confidence=obj.confidence,
            existing_page_id=obj.notion_page_id,
        )
        set_objective_notion_page_id(obj.id, obj_res.notion_page_id)

        kr_out = []
        for kr in obj.krs:
            res = await notion_mod.push_kr(
                mcs_id=kr.id,
                name=kr.text,
                objective_notion_id=obj_res.notion_page_id,
                target=kr.target,
                current=kr.current,
                unit=kr.unit,
                status=kr.status,
                due=kr.due,
                quarter=obj.quarter,
                existing_page_id=kr.notion_page_id,
            )
            set_kr_notion_page_id(kr.id, res.notion_page_id)
            kr_out.append({"id": kr.id, "notion_page_id": res.notion_page_id})
    except (NotionError, NotionConfigError) as e:
        return {"error": str(e)}
    return {"objective": obj_res.notion_page_id, "krs": kr_out}


@mcp.tool(
    name="notion.push_daily_tasks",
    description=(
        "Create daily_tasks rows. Each task dict keys: task (required), "
        "date (YYYY-MM-DD required), time_start, time_end, status, kr_id "
        "(mcs kr-id), priority (must|should|could), quantity, notes, source."
    ),
)
async def notion_push_daily_tasks(
    tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    inputs: list[DailyTaskInput] = []
    for t in tasks:
        kr_notion_id = None
        if t.get("kr_id"):
            try:
                kr = core_okr_get_kr(str(t["kr_id"]))
                kr_notion_id = kr.notion_page_id
            except (OKRError, OKRNotFound):
                return {"error": f"unknown kr_id {t.get('kr_id')!r}"}
            if not kr_notion_id:
                return {
                    "error": (
                        f"kr {t['kr_id']!r} has no notion_page_id — "
                        f"run okr.push on its Objective first."
                    )
                }
        inputs.append(
            DailyTaskInput(
                task=str(t["task"]),
                date=str(t["date"]),
                time_start=t.get("time_start"),
                time_end=t.get("time_end"),
                status=str(t.get("status") or "todo"),
                kr_notion_id=kr_notion_id,
                priority=t.get("priority"),
                quantity=t.get("quantity"),
                notes=t.get("notes"),
                source=str(t.get("source") or "mcs-brief"),
            )
        )
    try:
        ids = await notion_mod.push_daily_tasks(inputs)
    except (NotionError, NotionConfigError) as e:
        return {"error": str(e)}
    return {"created": ids}


@mcp.tool(
    name="notion.push_capture",
    description=(
        "Upsert a capture to mcs_captures. Reads frontmatter `tasks` (list of"
        " Notion daily_task page ids written by memory.add_task_link) and"
        " writes them as the Notion Tasks relation. Returns {notion_page_id}"
        " or {error}."
    ),
)
async def notion_push_capture(capture_id: str) -> dict[str, Any]:
    try:
        memo = load_memo(capture_id)
    except (MemoNotFound, MemoAmbiguous) as e:
        return {"error": str(e)}

    import frontmatter as _fm
    meta = (_fm.load(memo.path).metadata) or {}
    task_notion_ids: list[str] = [
        str(t).strip()
        for t in (meta.get("tasks") or [])
        if t and str(t).strip()
    ]

    cap_input = CaptureInput(
        mcs_id=memo.id,
        text=memo.body,
        type=memo.type or "signal",
        domain=memo.domain,
        created=(memo.created_at or "")[:10] or memo.id[:10],
        entities=memo.entities,
        source=memo.source or "typed",
        task_notion_ids=task_notion_ids,
    )
    try:
        result = await notion_mod.push_capture(cap_input)
    except (NotionError, NotionConfigError) as e:
        return {"error": str(e)}
    return {"notion_page_id": result.notion_page_id}


def run_server(
    host: str | None = None,
    port: int | None = None,
    *,
    watch: bool = True,
) -> None:
    """Start the MCP HTTP server. Blocks until the process is killed.

    When `watch` is True (default), the server's lifespan hook also spawns
    the brain/ filesystem watcher — so external file drops get indexed
    live. Running watcher inside the server guarantees a single MemSearch
    owner (solves Milvus Lite single-process lock) and a single asyncio
    loop owner (keeps memsearch's cached httpx clients usable).
    """
    settings = load_settings()
    h = host or settings.daemon_host
    p = port or settings.daemon_port

    global _watch_enabled
    _watch_enabled = watch

    mcp.run(transport="http", host=h, port=p)


if __name__ == "__main__":
    run_server()
