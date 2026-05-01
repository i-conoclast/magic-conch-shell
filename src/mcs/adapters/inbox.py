"""Generic suggestion inbox (FR-G3).

Single rendering layer over multiple "things waiting for user review":

- entity drafts (FR-C1, source: brain/entities/drafts/)
- skill-promotion drafts (FR-E5, source: .brain/skill-suggestions/, Phase 11)
- entity merge suggestions (FR-C5, future)

The inbox itself stores **nothing** — each item type owns its own
persistence. `list_pending()` aggregates across sources; `act()`
dispatches the user's verdict (approve / reject / defer) back to the
owning adapter. This keeps the existing entity-draft flow untouched
while still giving evening-retro a unified surface.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcs.adapters import entity as entity_mod
from mcs.adapters import skill_suggestion as skill_sug_mod


# ─── data ──────────────────────────────────────────────────────────────

@dataclass
class InboxItem:
    """One pending suggestion, source-agnostic."""

    type: str             # "entity-draft" | "skill-promotion" | ...
    id: str               # type-scoped identifier (entity qualified, skill slug, …)
    summary: str          # one-line label for display
    created_at: str       # ISO timestamp; controls list ordering
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "id": self.id,
            "summary": self.summary,
            "created_at": self.created_at,
            "payload": self.payload,
        }


# ─── errors ────────────────────────────────────────────────────────────

class InboxError(Exception):
    """Base class for inbox dispatch errors."""


class UnknownItemType(InboxError):
    """The given `type` has no registered handler."""


# ─── source: entity drafts ─────────────────────────────────────────────

def _list_entity_drafts() -> list[InboxItem]:
    out: list[InboxItem] = []
    for ref in entity_mod.list_drafts():
        meta = ref.meta or {}
        bits = []
        for k in ("role", "company", "url", "relation"):
            v = meta.get(k)
            if v:
                bits.append(f"{k}={v}")
        conf = meta.get("detection_confidence")
        if conf is not None:
            bits.append(f"conf={conf}")
        suffix = f" · {', '.join(bits)}" if bits else ""
        summary = f"{ref.qualified} — {ref.name!r}{suffix}"
        out.append(
            InboxItem(
                type="entity-draft",
                id=ref.qualified,
                summary=summary,
                created_at=str(meta.get("detected_at") or ""),
                payload={
                    "kind": ref.kind,
                    "slug": ref.slug,
                    "name": ref.name,
                    "promoted_from": meta.get("promoted_from"),
                    "detection_confidence": conf,
                },
            )
        )
    return out


def _confirm_entity_draft(
    item_id: str, *, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    ref = entity_mod.confirm(item_id, extra=extra or None)
    return {"type": "entity-draft", "id": ref.qualified, "status": "confirmed"}


def _reject_entity_draft(item_id: str, *, reason: str | None = None) -> dict[str, Any]:
    record = entity_mod.reject(item_id, reason=reason)
    return {
        "type": "entity-draft",
        "id": f"{record['kind']}/{record['slug']}",
        "status": "rejected",
        "reason": reason,
    }


# ─── dispatch table (source registry) ──────────────────────────────────
#
# To add a new source (e.g. skill-promotion in Phase 11):
#   _SOURCES[<type>] = (<list_fn>, <confirm_fn>, <reject_fn>)
# Each list_fn returns list[InboxItem]. confirm/reject take (item_id, **kwargs).

def _list_skill_suggestions() -> list[InboxItem]:
    out: list[InboxItem] = []
    for sug in skill_sug_mod.list_drafts():
        meta = sug.meta or {}
        bits = []
        if sug.summary:
            bits.append(sug.summary)
        if sug.source_session_id:
            bits.append(f"session={sug.source_session_id}")
        suffix = f" — {' · '.join(bits)}" if bits else ""
        summary = f"{sug.slug} — {sug.name!r}{suffix}"
        out.append(
            InboxItem(
                type="skill-promotion",
                id=sug.slug,
                summary=summary,
                created_at=sug.detected_at,
                payload={
                    "slug": sug.slug,
                    "name": sug.name,
                    "draft_path": str(sug.path),
                    "source_session_id": sug.source_session_id,
                    "summary": sug.summary,
                },
            )
        )
    return out


def _confirm_skill_suggestion(
    item_id: str, *, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    target_dir = "planner"
    if extra and "target_dir" in extra:
        target_dir = str(extra["target_dir"])
    return skill_sug_mod.confirm(item_id, target_dir=target_dir)


def _reject_skill_suggestion(
    item_id: str, *, reason: str | None = None
) -> dict[str, Any]:
    return skill_sug_mod.reject(item_id, reason=reason)


_SOURCES: dict[str, tuple] = {
    "entity-draft": (
        _list_entity_drafts,
        _confirm_entity_draft,
        _reject_entity_draft,
    ),
    "skill-promotion": (
        _list_skill_suggestions,
        _confirm_skill_suggestion,
        _reject_skill_suggestion,
    ),
}


# ─── public API ────────────────────────────────────────────────────────

def list_pending(*, item_type: str | None = None) -> list[InboxItem]:
    """Return every pending item across all sources, newest first.

    Optional `item_type` filter lets callers narrow to a single source
    (the inbox-approve skill uses this to page through one type at a
    time when the queue grows).
    """
    items: list[InboxItem] = []
    for t, (list_fn, _, _) in _SOURCES.items():
        if item_type and t != item_type:
            continue
        items.extend(list_fn())
    items.sort(key=lambda it: it.created_at, reverse=True)
    return items


def act(
    item_type: str,
    item_id: str,
    action: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Dispatch a user verdict to the owning adapter.

    Actions:
      - "approve" / "confirm" — calls the type's confirm handler
      - "reject"              — calls the type's reject handler
      - "defer" / "later"     — no-op; item stays in the queue

    Extra kwargs are forwarded:
      - confirm: `extra` (dict of supplemental fields, type-specific)
      - reject:  `reason` (str)
    """
    handlers = _SOURCES.get(item_type)
    if not handlers:
        raise UnknownItemType(f"unknown inbox item type {item_type!r}")
    _, confirm, reject = handlers

    if action in ("approve", "confirm"):
        return confirm(item_id, **kwargs)
    if action == "reject":
        return reject(item_id, **kwargs)
    if action in ("defer", "later", "skip"):
        return {"type": item_type, "id": item_id, "status": "deferred"}
    raise InboxError(f"unknown action {action!r}")


__all__ = [
    "InboxError",
    "InboxItem",
    "UnknownItemType",
    "act",
    "list_pending",
]
