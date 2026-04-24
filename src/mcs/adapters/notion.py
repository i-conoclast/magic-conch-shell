"""Notion adapter — mcs writes to its own Notion DBs.

Four DBs (created manually by the user, shared with the
`magic-conch-shell` Notion integration):
  - mcs_okr_master     — Objective pages
  - mcs_kr_tracker     — KR pages (synced relations: Objective, tasks, Captures)
  - mcs_daily_tasks    — daily task pages (plan-tracker-style props)
  - mcs_captures       — capture pages (multi-select entities)

Design notes:
  - We only upsert by mcs id (frontmatter-stored `notion_page_id`).
  - Property builders live together so schema changes are local.
  - Rate-limit aware: each write sleeps 0.35s to stay under Notion's
    3 req/sec soft limit across batch operations.
  - All failures bubble up as NotionError — callers decide whether to
    degrade gracefully (e.g. capture) or abort (e.g. okr push).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import httpx

from mcs.config import load_settings


_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"
_RATE_SLEEP_S = 0.35  # ~3 writes/sec

logger = logging.getLogger(__name__)


class NotionError(RuntimeError):
    """Generic Notion API failure (HTTP error, missing config, etc.)."""


class NotionConfigError(NotionError):
    """Required token / DB id missing."""


@dataclass
class DBConfig:
    token: str
    okr_master_db: str
    kr_tracker_db: str
    daily_tasks_db: str
    captures_db: str


def _cfg() -> DBConfig:
    s = load_settings()
    missing = []
    if not s.mcs_notion_token:
        missing.append("MCS_NOTION_TOKEN")
    if not s.mcs_notion_okr_master_db:
        missing.append("MCS_NOTION_OKR_MASTER_DB")
    if not s.mcs_notion_kr_tracker_db:
        missing.append("MCS_NOTION_KR_TRACKER_DB")
    if not s.mcs_notion_daily_tasks_db:
        missing.append("MCS_NOTION_DAILY_TASKS_DB")
    if not s.mcs_notion_captures_db:
        missing.append("MCS_NOTION_CAPTURES_DB")
    if missing:
        raise NotionConfigError(
            f"missing Notion config: {', '.join(missing)}. "
            f"See README for setup instructions."
        )
    return DBConfig(
        token=s.mcs_notion_token or "",
        okr_master_db=s.mcs_notion_okr_master_db or "",
        kr_tracker_db=s.mcs_notion_kr_tracker_db or "",
        daily_tasks_db=s.mcs_notion_daily_tasks_db or "",
        captures_db=s.mcs_notion_captures_db or "",
    )


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


# ─── property builders ─────────────────────────────────────────────────

def _title(text: str) -> dict:
    return {"title": [{"type": "text", "text": {"content": text[:2000]}}]}


def _rich_text(text: str) -> dict:
    return {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}


def _number(n: float | int | None) -> dict:
    return {"number": None if n is None else float(n)}


def _select(value: str | None) -> dict:
    return {"select": None if not value else {"name": value}}


def _status(value: str | None) -> dict:
    """Notion's built-in Status property — different shape from select."""
    return {"status": None if not value else {"name": value}}


def _multi_select(values: Iterable[str]) -> dict:
    return {"multi_select": [{"name": v} for v in values if v]}


def _date(start: str | None, end: str | None = None) -> dict:
    if not start:
        return {"date": None}
    payload: dict[str, Any] = {"start": start}
    if end:
        payload["end"] = end
    return {"date": payload}


def _relation(page_ids: Iterable[str]) -> dict:
    return {"relation": [{"id": pid} for pid in page_ids if pid]}


# ─── HTTP ───────────────────────────────────────────────────────────────

async def _request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    json: dict | None = None,
) -> dict:
    r = await client.request(method, f"{_API_BASE}{path}", json=json)
    if r.status_code >= 400:
        raise NotionError(f"Notion {method} {path}: {r.status_code} {r.text[:300]}")
    return r.json()


async def _query_by_id(
    client: httpx.AsyncClient, db_id: str, id_value: str
) -> str | None:
    """Find an existing page in `db_id` whose `ID` property equals `id_value`."""
    payload = {
        "filter": {"property": "ID", "rich_text": {"equals": id_value}},
        "page_size": 1,
    }
    body = await _request(
        client, "POST", f"/databases/{db_id}/query", json=payload
    )
    results = body.get("results") or []
    return results[0]["id"] if results else None


async def _upsert(
    client: httpx.AsyncClient,
    db_id: str,
    id_value: str,
    properties: dict,
    *,
    id_prop: str = "ID",
    existing_page_id: str | None = None,
) -> str:
    """Create or update a page in `db_id`.

    Lookup order:
      1. `existing_page_id` if provided (caller remembers it).
      2. Query by `id_prop` = id_value.
      3. Fallthrough → create new.

    Returns the resulting page id.
    """
    target = existing_page_id
    if target is None:
        target = await _query_by_id(client, db_id, id_value)

    if target:
        resp = await _request(
            client,
            "PATCH",
            f"/pages/{target}",
            json={"properties": properties},
        )
        return resp["id"]
    resp = await _request(
        client,
        "POST",
        "/pages",
        json={
            "parent": {"database_id": db_id},
            "properties": properties,
        },
    )
    await asyncio.sleep(_RATE_SLEEP_S)
    return resp["id"]


# ─── Public push APIs ──────────────────────────────────────────────────

@dataclass
class PushResult:
    id: str               # mcs id (unchanged)
    notion_page_id: str   # resulting Notion page id


async def push_objective(
    *,
    mcs_id: str,
    name: str,
    quarter: str,
    domain: str,
    status: str,
    confidence: float,
    existing_page_id: str | None = None,
) -> PushResult:
    """Create or update an Objective row in mcs_okr_master."""
    cfg = _cfg()
    props = {
        "Name": _title(name),
        "ID": _rich_text(mcs_id),
        "Quarter": _select(quarter),
        "Domain": _select(domain),
        "Status": _select(status),
        "Confidence": _number(confidence),
    }
    async with httpx.AsyncClient(
        timeout=30.0, headers=_headers(cfg.token)
    ) as c:
        page_id = await _upsert(
            c,
            cfg.okr_master_db,
            mcs_id,
            props,
            existing_page_id=existing_page_id,
        )
    return PushResult(id=mcs_id, notion_page_id=page_id)


async def push_kr(
    *,
    mcs_id: str,
    name: str,
    objective_notion_id: str | None,
    target: float,
    current: float,
    unit: str,
    status: str,
    due: str | None,
    quarter: str,
    existing_page_id: str | None = None,
) -> PushResult:
    """Create or update a KR row in mcs_kr_tracker.

    `objective_notion_id` links the KR to its Objective via the
    synced `Objective` relation — must be a Notion page id from a
    previous `push_objective()` call.
    """
    cfg = _cfg()
    props: dict[str, Any] = {
        "Name": _title(name),
        "ID": _rich_text(mcs_id),
        "Target": _number(target),
        "Current": _number(current),
        "Unit": _select(unit),
        "Status": _select(status),
        "Due": _date(due),
        "Quarter": _select(quarter),
    }
    if objective_notion_id:
        props["Objective"] = _relation([objective_notion_id])

    async with httpx.AsyncClient(
        timeout=30.0, headers=_headers(cfg.token)
    ) as c:
        page_id = await _upsert(
            c,
            cfg.kr_tracker_db,
            mcs_id,
            props,
            existing_page_id=existing_page_id,
        )
    return PushResult(id=mcs_id, notion_page_id=page_id)


@dataclass
class DailyTaskInput:
    task: str
    date: str                          # YYYY-MM-DD
    time_start: str | None = None      # HH:MM — embedded into `일시`
    time_end: str | None = None
    status: str = "todo"               # Notion's status property
    kr_notion_id: str | None = None
    priority: str | None = None        # must / should / could
    quantity: float | None = None
    notes: str | None = None
    source: str = "mcs-brief"
    mcs_id: str | None = None          # optional: external tracing id


async def push_daily_task(task: DailyTaskInput) -> str:
    """Create a single daily_tasks row. Returns the resulting page id.

    Daily tasks are append-only in the plan-tracker workflow (plan-tracker
    updates them by id later), so this function does NOT upsert — each
    call creates a fresh row. Callers dedupe upstream if needed.
    """
    cfg = _cfg()
    start = task.date
    if task.time_start:
        start = f"{task.date}T{task.time_start}:00+09:00"
    end = None
    if task.time_end:
        end = f"{task.date}T{task.time_end}:00+09:00"

    props: dict[str, Any] = {
        "Task": _title(task.task),
        "일시": _date(start, end),
        "Status": _status(task.status),
        "Source": _rich_text(task.source),
    }
    if task.kr_notion_id:
        props["KR"] = _relation([task.kr_notion_id])
    if task.priority:
        props["우선순위"] = _select(task.priority)
    if task.quantity is not None:
        props["수량"] = _number(task.quantity)
    if task.notes:
        props["메모"] = _rich_text(task.notes)

    async with httpx.AsyncClient(
        timeout=30.0, headers=_headers(cfg.token)
    ) as c:
        resp = await _request(
            c,
            "POST",
            "/pages",
            json={
                "parent": {"database_id": cfg.daily_tasks_db},
                "properties": props,
            },
        )
        await asyncio.sleep(_RATE_SLEEP_S)
    return resp["id"]


async def push_daily_tasks(tasks: Sequence[DailyTaskInput]) -> list[str]:
    """Batch push — returns list of Notion page ids in the same order."""
    out: list[str] = []
    for t in tasks:
        out.append(await push_daily_task(t))
    return out


@dataclass
class CaptureInput:
    mcs_id: str                         # capture id (used as Notion Title)
    text: str
    type: str                           # signal / note
    domain: str | None
    created: str                        # YYYY-MM-DD
    entities: list[str] = field(default_factory=list)
    source: str = "typed"
    kr_notion_ids: list[str] = field(default_factory=list)
    existing_page_id: str | None = None


async def push_capture(cap: CaptureInput) -> PushResult:
    """Upsert a capture row in mcs_captures.

    `ID` is the Title property (capture id); we use it directly for
    lookup instead of a separate `ID` rich_text property.
    """
    cfg = _cfg()
    props: dict[str, Any] = {
        "ID": _title(cap.mcs_id),
        "Text": _rich_text(cap.text),
        "Type": _select(cap.type),
        "Domain": _select(cap.domain) if cap.domain else {"select": None},
        "Created": _date(cap.created),
        "Source": _select(cap.source),
        "Entities": _multi_select(cap.entities),
    }
    if cap.kr_notion_ids:
        props["KRs"] = _relation(cap.kr_notion_ids)

    async with httpx.AsyncClient(
        timeout=30.0, headers=_headers(cfg.token)
    ) as c:
        # Captures use the Title property as their ID; query accordingly.
        page_id = cap.existing_page_id
        if page_id is None:
            payload = {
                "filter": {"property": "ID", "title": {"equals": cap.mcs_id}},
                "page_size": 1,
            }
            body = await _request(
                c, "POST", f"/databases/{cfg.captures_db}/query", json=payload
            )
            results = body.get("results") or []
            page_id = results[0]["id"] if results else None

        if page_id:
            resp = await _request(
                c, "PATCH", f"/pages/{page_id}", json={"properties": props}
            )
        else:
            resp = await _request(
                c,
                "POST",
                "/pages",
                json={
                    "parent": {"database_id": cfg.captures_db},
                    "properties": props,
                },
            )
            await asyncio.sleep(_RATE_SLEEP_S)
    return PushResult(id=cap.mcs_id, notion_page_id=resp["id"])
