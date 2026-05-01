"""Entity operations — drafts, profiles, back-links.

SSoT layout (under `brain/entities/`):
- `brain/entities/{kind}/{slug}.md`              — active profile
- `brain/entities/drafts/{kind}/{slug}.md`       — pending approval

Active vs draft is signalled by directory + a `status: draft` frontmatter
key on draft files only. Schema-less per kind: callers may pass arbitrary
extra fields (role, company, url, ...). Only `kind`, `slug`, `name`,
`created_at` are guaranteed.

Functions intentionally stay LLM-free; entity *detection* lives in the
Hermes `entity-extract` skill (FR-C1), which calls into these functions
via the daemon's MCP tools.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import frontmatter

from mcs.adapters.memory import _kebab, now_kst
from mcs.config import load_settings


# ─── kinds ──────────────────────────────────────────────────────────────

# FR-C1 calls out four canonical kinds. We accept anything kebab-safe so
# that future detectors (e.g. `tools`, `papers`) can use the same plumbing
# without a code change, but we surface a hint when an unknown kind shows
# up so typos surface in tests.
KNOWN_KINDS: frozenset[str] = frozenset({"people", "companies", "jobs", "books"})


# ─── back-link AUTO section markers ─────────────────────────────────────

_AUTO_START = "<!-- AUTO-GENERATED BELOW. DO NOT EDIT. -->"
_AUTO_END = "<!-- END AUTO-GENERATED -->"


# ─── errors ─────────────────────────────────────────────────────────────

class EntityError(Exception):
    """Base class for entity-adapter errors."""


class EntityNotFound(EntityError):
    """No entity (active or draft) matches a slug query."""


class EntityAmbiguous(EntityError):
    """A bare slug matches multiple kinds; caller must use `kind/slug`."""

    def __init__(self, slug: str, candidates: list[str]) -> None:
        super().__init__(
            f"{slug!r} matches multiple entities: {candidates}. "
            f"Use `kind/slug` form."
        )
        self.candidates = candidates


class EntityAlreadyExists(EntityError):
    """A confirm/move would overwrite an existing active profile."""


# ─── data ───────────────────────────────────────────────────────────────

@dataclass
class EntityRef:
    """Lightweight handle for an entity profile (active or draft)."""

    kind: str
    slug: str
    name: str
    status: str            # "active" | "draft"
    path: Path
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def qualified(self) -> str:
        return f"{self.kind}/{self.slug}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "slug": self.slug,
            "name": self.name,
            "status": self.status,
            "path": str(self.path),
            "meta": self.meta,
        }


# ─── path helpers ──────────────────────────────────────────────────────

def _entities_root() -> Path:
    return load_settings().brain_dir.resolve() / "entities"


def _drafts_root() -> Path:
    return _entities_root() / "drafts"


def _profile_path(kind: str, slug: str, *, draft: bool) -> Path:
    base = _drafts_root() if draft else _entities_root()
    return base / kind / f"{slug}.md"


def _split_qualified(query: str) -> tuple[str | None, str]:
    """Parse a `kind/slug` query. Returns (kind_or_None, slug)."""
    q = query.strip()
    if "/" in q:
        head, tail = q.split("/", 1)
        return head, tail
    return None, q


def _scan_kinds(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and p.name != "drafts")


def _slug_from_name(name: str) -> str:
    slug = _kebab(name)
    if not slug:
        raise ValueError(f"cannot derive slug from name {name!r}")
    return slug


# ─── lookup ────────────────────────────────────────────────────────────

def resolve_entity(query: str) -> EntityRef:
    """Locate an entity by `kind/slug` or bare `slug`. Active beats draft."""
    kind, slug = _split_qualified(query)

    if kind is not None:
        # Exact kind given; check active then draft.
        for draft in (False, True):
            p = _profile_path(kind, slug, draft=draft)
            if p.exists():
                return _load_ref(p, kind=kind, slug=slug, draft=draft)
        raise EntityNotFound(f"no entity at {query!r}")

    # Bare slug — search every kind, prefer active.
    matches: list[tuple[str, bool, Path]] = []
    for draft in (False, True):
        root = _drafts_root() if draft else _entities_root()
        for k in _scan_kinds(root):
            p = root / k / f"{slug}.md"
            if p.exists():
                matches.append((k, draft, p))
        if matches:
            # Active matches found — don't fall through to draft scan.
            break

    if not matches:
        raise EntityNotFound(f"no entity with slug {slug!r}")
    if len(matches) > 1:
        raise EntityAmbiguous(slug, [f"{m[0]}/{slug}" for m in matches])
    k, draft, p = matches[0]
    return _load_ref(p, kind=k, slug=slug, draft=draft)


def _resolve_draft(query: str) -> EntityRef:
    """Locate a *draft* entity, ignoring any same-slug active profile."""
    kind, slug = _split_qualified(query)
    if kind is not None:
        p = _profile_path(kind, slug, draft=True)
        if p.exists():
            return _load_ref(p, kind=kind, slug=slug, draft=True)
        raise EntityNotFound(f"no draft at {query!r}")

    matches: list[tuple[str, Path]] = []
    draft_root = _drafts_root()
    for k in _scan_kinds(draft_root):
        p = draft_root / k / f"{slug}.md"
        if p.exists():
            matches.append((k, p))
    if not matches:
        raise EntityNotFound(f"no draft with slug {slug!r}")
    if len(matches) > 1:
        raise EntityAmbiguous(slug, [f"{k}/{slug}" for k, _ in matches])
    k, p = matches[0]
    return _load_ref(p, kind=k, slug=slug, draft=True)


def _load_ref(path: Path, *, kind: str, slug: str, draft: bool) -> EntityRef:
    post = frontmatter.load(path)
    meta = dict(post.metadata or {})
    return EntityRef(
        kind=kind,
        slug=slug,
        name=str(meta.get("name") or slug),
        status="draft" if draft else "active",
        path=path.resolve(),
        meta=meta,
    )


def entity_exists(query: str) -> bool:
    try:
        resolve_entity(query)
    except EntityError:
        return False
    return True


# ─── listing ────────────────────────────────────────────────────────────

def list_entities(
    *,
    kind: str | None = None,
    include_drafts: bool = False,
    drafts_only: bool = False,
) -> list[EntityRef]:
    """List active entities (and/or drafts)."""
    out: list[EntityRef] = []

    if not drafts_only:
        active_root = _entities_root()
        for k in _scan_kinds(active_root):
            if kind and k != kind:
                continue
            for p in sorted((active_root / k).glob("*.md")):
                out.append(_load_ref(p, kind=k, slug=p.stem, draft=False))

    if include_drafts or drafts_only:
        draft_root = _drafts_root()
        for k in _scan_kinds(draft_root):
            if kind and k != kind:
                continue
            for p in sorted((draft_root / k).glob("*.md")):
                out.append(_load_ref(p, kind=k, slug=p.stem, draft=True))

    return out


def list_drafts(*, kind: str | None = None) -> list[EntityRef]:
    """Convenience wrapper for the approval-inbox flow."""
    return list_entities(kind=kind, drafts_only=True)


# ─── create ─────────────────────────────────────────────────────────────

def create_draft(
    kind: str,
    name: str,
    *,
    slug: str | None = None,
    detected_at: str | None = None,
    detection_confidence: float | None = None,
    promoted_from: str | None = None,
    extra: dict[str, Any] | None = None,
) -> EntityRef:
    """Create (or surface) a draft entity profile.

    Idempotent: if an active or draft profile already exists at the target
    `(kind, slug)`, return the existing ref unchanged. This matches FR-C1
    "이미 초안 또는 정식 엔티티에 존재하는 이름은 중복 생성되지 않음".
    """
    if not kind or "/" in kind:
        raise ValueError(f"invalid kind {kind!r}")
    final_slug = slug or _slug_from_name(name)

    # Idempotency check first — don't overwrite an existing record.
    for draft in (False, True):
        existing = _profile_path(kind, final_slug, draft=draft)
        if existing.exists():
            return _load_ref(existing, kind=kind, slug=final_slug, draft=draft)

    meta: dict[str, Any] = {
        "kind": kind,
        "slug": final_slug,
        "name": name,
        "status": "draft",
        "detected_at": detected_at or now_kst().isoformat(),
    }
    if detection_confidence is not None:
        meta["detection_confidence"] = float(detection_confidence)
    if promoted_from:
        meta["promoted_from"] = promoted_from
    if extra:
        for k, v in extra.items():
            if k in meta or v is None:
                continue
            meta[k] = v

    body = (
        "## Context\n"
        "_(승인 시 작성)_\n\n"
        "## Back-links (auto)\n"
        f"{_AUTO_START}\n"
        f"{_AUTO_END}\n"
    )

    target = _profile_path(kind, final_slug, draft=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        frontmatter.dumps(frontmatter.Post(body, **meta)) + "\n",
        encoding="utf-8",
    )
    return _load_ref(target, kind=kind, slug=final_slug, draft=True)


# ─── confirm / reject ──────────────────────────────────────────────────

def confirm(query: str, *, extra: dict[str, Any] | None = None) -> EntityRef:
    """Promote a draft to an active profile.

    Strips draft-only fields (`status`, `detected_at`,
    `detection_confidence`) and merges any user-provided `extra` fields.
    Raises `EntityNotFound` when no draft matches and `EntityAlreadyExists`
    when a target active profile would be overwritten.
    """
    ref = _resolve_draft(query)
    target = _profile_path(ref.kind, ref.slug, draft=False)
    if target.exists():
        raise EntityAlreadyExists(
            f"active entity already at {ref.kind}/{ref.slug}; "
            f"merge or rename before confirming the draft."
        )

    post = frontmatter.load(ref.path)
    meta = dict(post.metadata or {})
    for k in ("status", "detected_at", "detection_confidence"):
        meta.pop(k, None)
    now_iso = now_kst().isoformat()
    meta.setdefault("created_at", now_iso)
    meta["updated_at"] = now_iso
    if extra:
        for k, v in extra.items():
            if v is None:
                continue
            meta[k] = v

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        frontmatter.dumps(frontmatter.Post(post.content or "", **meta)) + "\n",
        encoding="utf-8",
    )
    ref.path.unlink()
    return _load_ref(target, kind=ref.kind, slug=ref.slug, draft=False)


def reject(query: str, *, reason: str | None = None) -> dict[str, Any]:
    """Delete a draft and append a rejection record to .brain/."""
    try:
        ref = _resolve_draft(query)
    except EntityNotFound:
        # Maybe the user passed a slug that resolves to an active entity —
        # surface a clearer message instead of "draft not found".
        if entity_exists(query):
            raise EntityError(
                f"refuse to reject an active entity ({query!r}); "
                f"use a dedicated delete command instead."
            ) from None
        raise

    settings = load_settings()
    log_path = settings.cache_dir.resolve() / "rejected-entities.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "kind": ref.kind,
        "slug": ref.slug,
        "name": ref.name,
        "rejected_at": now_kst().isoformat(),
        "reason": reason,
    }
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    ref.path.unlink()
    return record


# ─── back-links ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _BacklinkLine:
    rel: str        # `domains/career/2026-04-22-foo` (no .md)
    date: str       # `2026-04-22` (sortable)
    type: str       # `note` | `signal` | …

    def render(self) -> str:
        return f"- [[{self.rel}]] ({self.date}, {self.type})"


_BACKLINK_RE = re.compile(
    r"^- \[\[(?P<rel>[^\]]+)\]\] \((?P<date>\d{4}-\d{2}-\d{2}), (?P<type>[^)]+)\)$"
)


def _record_descriptor(record_path: Path) -> _BacklinkLine | None:
    """Build a back-link line from a brain record's frontmatter."""
    settings = load_settings()
    brain = settings.brain_dir.resolve()
    record_path = record_path.resolve()
    try:
        rel = record_path.relative_to(brain).with_suffix("").as_posix()
    except ValueError:
        return None

    try:
        post = frontmatter.load(record_path)
    except Exception:
        return None
    meta = post.metadata or {}
    created_at = str(meta.get("created_at") or "")
    date = created_at[:10] if created_at else ""
    rec_type = str(meta.get("type") or "note")
    if not date:
        return None
    return _BacklinkLine(rel=rel, date=date, type=rec_type)


def _read_auto_section(path: Path) -> tuple[str, list[str], str]:
    """Return (head, lines_in_auto, tail) for an entity profile."""
    text = path.read_text(encoding="utf-8")
    start = text.find(_AUTO_START)
    end = text.find(_AUTO_END)
    if start == -1 or end == -1 or end < start:
        # Profile lacks AUTO markers — append a fresh section.
        head = text.rstrip() + "\n\n## Back-links (auto)\n"
        return head + _AUTO_START + "\n", [], "\n" + _AUTO_END + "\n"

    head = text[: start + len(_AUTO_START)] + "\n"
    inner = text[start + len(_AUTO_START):end]
    tail = text[end:]
    lines = [ln for ln in (l.strip() for l in inner.splitlines()) if ln]
    return head, lines, tail


def _write_auto_section(path: Path, head: str, lines: list[str], tail: str) -> None:
    body = head + ("\n".join(lines) + "\n" if lines else "") + tail
    path.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")


def _bump_updated_at(path: Path) -> None:
    """Set frontmatter `updated_at` = now KST. No-op for malformed YAML."""
    try:
        post = frontmatter.load(path)
    except Exception:
        return
    meta = dict(post.metadata or {})
    meta["updated_at"] = now_kst().isoformat()
    path.write_text(
        frontmatter.dumps(frontmatter.Post(post.content or "", **meta)) + "\n",
        encoding="utf-8",
    )


def add_backlink(query: str, record_path: Path | str) -> bool:
    """Insert a back-link entry on an entity profile. Idempotent.

    Returns True if the line was added, False if it was already present
    or if the entity could not be located (silent no-op — the manual
    `-e` capture flow shouldn't fail just because an entity profile
    hasn't been created yet).
    """
    try:
        ref = resolve_entity(query)
    except EntityError:
        return False

    descriptor = _record_descriptor(Path(record_path))
    if descriptor is None:
        return False

    head, lines, tail = _read_auto_section(ref.path)
    new_line = descriptor.render()
    if new_line in lines:
        return False
    lines.append(new_line)
    lines.sort(key=_extract_date_key, reverse=True)
    _write_auto_section(ref.path, head, lines, tail)
    _bump_updated_at(ref.path)
    return True


def remove_backlink(query: str, record_path: Path | str) -> bool:
    """Drop a back-link entry. Returns True when something was removed."""
    try:
        ref = resolve_entity(query)
    except EntityError:
        return False

    settings = load_settings()
    brain = settings.brain_dir.resolve()
    try:
        rel = Path(record_path).resolve().relative_to(brain).with_suffix("").as_posix()
    except ValueError:
        return False

    head, lines, tail = _read_auto_section(ref.path)
    new_lines = [ln for ln in lines if _line_rel(ln) != rel]
    if len(new_lines) == len(lines):
        return False
    _write_auto_section(ref.path, head, new_lines, tail)
    _bump_updated_at(ref.path)
    return True


def _line_rel(line: str) -> str | None:
    m = _BACKLINK_RE.match(line)
    return m.group("rel") if m else None


def _extract_date_key(line: str) -> str:
    m = _BACKLINK_RE.match(line)
    return m.group("date") if m else ""


def rebuild_backlinks() -> int:
    """Clear every entity's AUTO section and re-derive from brain/ records.

    Returns the count of (entity, record) pairs linked. Used by
    `mcs reindex --backlinks` (FR-I2) and after FR-C5 merges.
    """
    settings = load_settings()
    brain = settings.brain_dir.resolve()

    for ref in list_entities(include_drafts=True):
        head, _, tail = _read_auto_section(ref.path)
        _write_auto_section(ref.path, head, [], tail)

    linked = 0
    for sub in ("signals", "domains", "daily", "plans"):
        root = brain / sub
        if not root.exists():
            continue
        for record in root.rglob("*.md"):
            try:
                post = frontmatter.load(record)
            except Exception:
                continue
            entities = list((post.metadata or {}).get("entities") or [])
            for slug in entities:
                if add_backlink(slug, record):
                    linked += 1
    return linked


# ─── public exports ────────────────────────────────────────────────────

__all__ = [
    "EntityAmbiguous",
    "EntityAlreadyExists",
    "EntityError",
    "EntityNotFound",
    "EntityRef",
    "KNOWN_KINDS",
    "add_backlink",
    "confirm",
    "create_draft",
    "entity_exists",
    "list_drafts",
    "list_entities",
    "rebuild_backlinks",
    "reject",
    "remove_backlink",
    "resolve_entity",
]
