"""Memory operations — capture, search, entities.

SSoT is `brain/` markdown files with YAML frontmatter.
Cache (`.brain/`) is rebuildable at any time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import frontmatter

from mcs.config import load_settings


KST = ZoneInfo("Asia/Seoul")

# 7 도메인 (03-functional A-capture-fr.md 기준)
DOMAINS: frozenset[str] = frozenset(
    {
        "career",
        "health-physical",
        "health-mental",
        "relationships",
        "finance",
        "ml",
        "general",
    }
)


@dataclass
class CaptureResult:
    """Result of a single capture operation."""

    path: Path
    id: str
    type: str
    domain: str | None


def now_kst() -> datetime:
    """Current time in KST (Asia/Seoul)."""
    return datetime.now(KST)


def _kebab(text: str, max_len: int = 50) -> str:
    """Lowercase kebab-case with Korean preserved. Strip punctuation."""
    # Keep Korean (Hangul Syllables + Jamo), ASCII alphanumerics; rest → hyphen.
    cleaned = re.sub(
        r"[^a-z0-9\u3131-\u318e\uac00-\ud7a3]+",
        "-",
        text.lower(),
    )
    cleaned = cleaned.strip("-")
    return cleaned[:max_len]


def generate_slug(
    now: datetime | None = None,
    title: str | None = None,
) -> str:
    """
    Slug rules (from docs/design/02-data-model.md):
      - With title   : YYYY-MM-DD-{kebab-title}   (human typed note)
      - Without title: YYYY-MM-DD-HHmmss          (auto)
    """
    now = now or now_kst()
    date_part = now.strftime("%Y-%m-%d")
    if title:
        kebab = _kebab(title)
        if kebab:
            return f"{date_part}-{kebab}"
    return now.strftime("%Y-%m-%d-%H%M%S")


def _target_folder(brain: Path, domain: str | None) -> Path:
    if domain:
        return brain / "domains" / domain
    return brain / "signals"


@dataclass
class ResolvedMemo:
    """A brain/ file located by id or path, with parsed frontmatter."""

    path: Path
    rel_path: str
    id: str
    type: str
    domain: str | None
    entities: list[str]
    created_at: str | None
    source: str | None
    body: str


class MemoNotFound(LookupError):
    """Raised when no brain/ file matches a lookup query."""


class MemoAmbiguous(LookupError):
    """Raised when a slug matches multiple files (e.g. same slug in different folders)."""

    def __init__(self, query: str, candidates: list[Path]) -> None:
        super().__init__(
            f"{query!r} matches {len(candidates)} files — disambiguate with a path prefix."
        )
        self.candidates = candidates


def _scan_brain(brain: Path) -> list[Path]:
    """Yield all brain/*.md under the scoped roots (signals + domains)."""
    out: list[Path] = []
    for sub in ("signals", "domains", "daily", "entities", "plans"):
        root = brain / sub
        if not root.exists():
            continue
        out.extend(root.rglob("*.md"))
    return out


def resolve_memo(query: str) -> Path:
    """Find the brain/ file for `query`.

    Accepts:
      - Bare slug (`2026-04-22-foo`) — matched against file stems.
      - Relative path under brain/ (`signals/2026-04-22-foo.md` or no .md).
      - Absolute path (only if inside brain/).

    Raises:
      MemoNotFound  — nothing matches.
      MemoAmbiguous — multiple files share the slug (rare: collision across folders).
    """
    settings = load_settings()
    brain = settings.brain_dir.resolve()
    q = query.strip()
    if q.startswith("brain/"):
        q = q[len("brain/"):]
    if q.endswith(".md"):
        q = q[:-3]

    # Path-like? (contains slash)
    if "/" in q:
        candidate = (brain / q).with_suffix(".md")
        if candidate.exists():
            return candidate.resolve()
        raise MemoNotFound(f"no file at brain/{q}.md")

    # Bare slug — scan for stem matches.
    matches = [p for p in _scan_brain(brain) if p.stem == q]
    if not matches:
        raise MemoNotFound(f"no brain file with id {q!r}")
    if len(matches) > 1:
        raise MemoAmbiguous(q, sorted(matches))
    return matches[0].resolve()


def load_memo(query: str) -> ResolvedMemo:
    """Resolve + parse a brain file by id or path."""
    path = resolve_memo(query)
    settings = load_settings()
    brain = settings.brain_dir.resolve()

    post = frontmatter.load(path)
    meta = post.metadata or {}
    inferred_type, inferred_domain = _infer_type_and_domain(brain, path)

    try:
        rel = str(path.relative_to(settings.repo_root.resolve()))
    except ValueError:
        rel = str(path)

    return ResolvedMemo(
        path=path,
        rel_path=rel,
        id=str(meta.get("id") or path.stem),
        type=str(meta.get("type") or inferred_type),
        domain=meta.get("domain") if meta.get("domain") is not None else inferred_domain,
        entities=list(meta.get("entities") or []),
        created_at=(str(meta["created_at"]) if "created_at" in meta else None),
        source=(str(meta["source"]) if "source" in meta else None),
        body=(post.content or "").strip(),
    )


@dataclass
class CaptureSummary:
    """Lightweight view of a capture for list/sync flows."""

    id: str
    path: Path
    rel_path: str
    type: str
    domain: str | None
    created_at: str
    entities: list[str]
    okrs: list[str]
    excerpt: str   # first non-empty content line, trimmed to 160 chars

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": str(self.path),
            "rel_path": self.rel_path,
            "type": self.type,
            "domain": self.domain,
            "created_at": self.created_at,
            "entities": self.entities,
            "okrs": self.okrs,
            "excerpt": self.excerpt,
        }


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def list_captures_by_date(
    date: str,
    *,
    domain: str | None = None,
    types: Iterable[str] | None = None,
) -> list[CaptureSummary]:
    """Return capture summaries whose frontmatter `created_at` falls on `date`.

    Args:
        date:    KST date string 'YYYY-MM-DD'.
        domain:  Optional frontmatter domain filter.
        types:   Optional type whitelist (default: {'signal', 'note'}).

    Scans brain/signals/ + brain/domains/ only — the capture surfaces
    we actually expect end-user memos in.
    """
    if not _DATE_RE.match(date):
        raise ValueError(f"date must be 'YYYY-MM-DD', got {date!r}")

    wanted_types = set(types) if types else {"signal", "note"}

    settings = load_settings()
    brain = settings.brain_dir.resolve()
    repo_root = settings.repo_root.resolve()

    roots = [brain / "signals"] + [brain / "domains" / d for d in sorted(DOMAINS)]

    out: list[CaptureSummary] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("*.md")):
            try:
                post = frontmatter.load(path)
            except Exception:
                continue
            meta = post.metadata or {}
            created = str(meta.get("created_at") or "")
            if not created.startswith(date):
                continue
            row_type = str(meta.get("type") or "")
            if wanted_types and row_type not in wanted_types:
                continue
            row_domain = meta.get("domain")
            if domain is not None and row_domain != domain:
                continue

            try:
                rel = str(path.resolve().relative_to(repo_root))
            except ValueError:
                rel = str(path)

            body = (post.content or "").strip()
            first_line = next(
                (ln.strip() for ln in body.splitlines() if ln.strip()),
                "",
            )
            excerpt = first_line[:160] + ("…" if len(first_line) > 160 else "")

            out.append(
                CaptureSummary(
                    id=str(meta.get("id") or path.stem),
                    path=path.resolve(),
                    rel_path=rel,
                    type=row_type,
                    domain=row_domain if row_domain is not None else None,
                    created_at=created,
                    entities=list(meta.get("entities") or []),
                    okrs=list(meta.get("okrs") or []),
                    excerpt=excerpt,
                )
            )
    return out


def set_domain(capture_id: str, domain: str | None) -> str | None:
    """Overwrite the `domain` frontmatter field on an existing brain/ record.

    Validates against the canonical DOMAINS set (None clears the field).
    Returns the new domain. No filesystem move (a record's path stays
    where it is — domain is purely a tag).

    This is the write path the Hermes domain-classify skill (FR-A3 / FR-C
    domain layer) uses to persist its inference. Because it bypasses
    `capture()`, no entity-extract webhook re-fires from this call —
    the skill's only side effect is the frontmatter mutation.
    """
    if domain is not None and domain not in DOMAINS:
        raise ValueError(
            f"Unknown domain {domain!r}. Valid: {sorted(DOMAINS)} or None."
        )

    path = resolve_memo(capture_id)
    post = frontmatter.load(path)
    meta = dict(post.metadata or {})
    if meta.get("domain") == domain:
        return domain  # idempotent
    meta["domain"] = domain
    path.write_text(
        frontmatter.dumps(frontmatter.Post(post.content or "", **meta)) + "\n",
        encoding="utf-8",
    )
    return domain


def add_okr_link(capture_id: str, kr_ids: Iterable[str]) -> list[str]:
    """Append kr_ids to a capture's frontmatter `okrs` field.

    Idempotent: existing links are preserved, duplicates are deduped.
    Returns the resulting full okrs list.
    """
    to_add = [s.strip() for s in kr_ids if s and s.strip()]
    if not to_add:
        # Still need to locate the capture even if no new links — fail loudly
        # when the capture doesn't exist so callers get a clear error.
        resolve_memo(capture_id)
        return []

    path = resolve_memo(capture_id)
    post = frontmatter.load(path)
    meta = dict(post.metadata or {})
    existing = list(meta.get("okrs") or [])
    merged: list[str] = list(existing)
    for kr in to_add:
        if kr not in merged:
            merged.append(kr)
    meta["okrs"] = merged
    path.write_text(
        frontmatter.dumps(frontmatter.Post(post.content or "", **meta)) + "\n",
        encoding="utf-8",
    )
    return merged


def add_task_link(capture_id: str, task_notion_ids: Iterable[str]) -> list[str]:
    """Append Notion task page ids to a capture's frontmatter `tasks` field.

    Mirrors `add_okr_link` shape — idempotent, deduped. Stores Notion
    page ids directly since tasks live in Notion (mcs_daily_tasks DB),
    not in brain/. The capture's `okrs` field still records intended
    KR linkage (legacy, but useful for capture-progress-sync matching).
    """
    to_add = [s.strip() for s in task_notion_ids if s and s.strip()]
    if not to_add:
        resolve_memo(capture_id)
        return []

    path = resolve_memo(capture_id)
    post = frontmatter.load(path)
    meta = dict(post.metadata or {})
    existing = list(meta.get("tasks") or [])
    merged: list[str] = list(existing)
    for tid in to_add:
        if tid not in merged:
            merged.append(tid)
    meta["tasks"] = merged
    path.write_text(
        frontmatter.dumps(frontmatter.Post(post.content or "", **meta)) + "\n",
        encoding="utf-8",
    )
    return merged


# ─── daily files ────────────────────────────────────────────────────────

def daily_file_path(date: str) -> Path:
    """Resolve the path for a daily note — brain/daily/YYYY/MM/DD.md.

    Does NOT create parent folders; callers handle creation on write.
    """
    if not _DATE_RE.match(date):
        raise ValueError(f"date must be 'YYYY-MM-DD', got {date!r}")
    settings = load_settings()
    brain = settings.brain_dir.resolve()
    year, month, day = date.split("-")
    return brain / "daily" / year / month / f"{day}.md"


def _daily_frontmatter(date: str) -> dict[str, Any]:
    """Minimum frontmatter for a fresh daily file."""
    return {
        "id": date,
        "type": "daily",
        "date": date,
        "created_at": now_kst().isoformat(),
        "source": "generated",
    }


def upsert_daily_section(date: str, heading: str, content: str) -> Path:
    """Replace (or append) a `## heading` section in the daily file.

    If the daily file does not exist, it is created with standard
    frontmatter plus the new section. If the heading already appears,
    its body (up to the next `## ` heading or EOF) is replaced. If
    not, the section is appended at the end.

    Returns the daily file path.
    """
    path = daily_file_path(date)
    path.parent.mkdir(parents=True, exist_ok=True)

    heading_line = f"## {heading}"
    section_body = content.rstrip() + "\n"

    if not path.exists():
        post = frontmatter.Post(
            f"{heading_line}\n\n{section_body}",
            **_daily_frontmatter(date),
        )
        path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
        return path

    post = frontmatter.load(path)
    body = post.content or ""
    lines = body.splitlines()

    # Find existing heading line (exact match).
    start = next(
        (i for i, ln in enumerate(lines) if ln.strip() == heading_line),
        -1,
    )
    if start == -1:
        # Append new section with a blank line separator.
        tail = "\n" if body.strip() else ""
        new_body = body.rstrip() + f"{tail}\n{heading_line}\n\n{section_body}"
    else:
        # Replace existing section body (lines after heading until next `## ` or EOF).
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j].startswith("## "):
                end = j
                break
        # Preserve blank lines before the next section by leaving the
        # separator between old end and next block alone.
        new_section = [heading_line, "", section_body.rstrip(), ""]
        new_lines = lines[:start] + new_section + lines[end:]
        new_body = "\n".join(new_lines).rstrip() + "\n"

    new_post = frontmatter.Post(new_body, **(post.metadata or {}))
    path.write_text(frontmatter.dumps(new_post) + "\n", encoding="utf-8")
    return path


def _infer_type_and_domain(brain: Path, path: Path) -> tuple[str, str | None]:
    """Derive (type, domain) from a file's location under brain/.

    brain/signals/X.md       → ("signal", None)
    brain/domains/Y/X.md     → ("note", "Y")
    anything else            → ("", None)  — caller decides what to do
    """
    try:
        rel = path.resolve().relative_to(brain.resolve())
    except ValueError:
        return "", None
    parts = rel.parts
    if len(parts) >= 1 and parts[0] == "signals":
        return "signal", None
    if len(parts) >= 3 and parts[0] == "domains":
        dom = parts[1]
        if dom in DOMAINS:
            return "note", dom
    return "", None


def supplement_frontmatter(path: Path, *, source: str = "file-watcher") -> bool:
    """Fill in missing frontmatter fields on an existing brain/ markdown file.

    Writes the file in-place when any required field is missing.
    Returns True if the file was rewritten, False otherwise.

    Required fields: id, type, domain, entities, created_at, source.

    Side effect (FR-C4.2 watcher path): regardless of whether anything
    was rewritten, any `entities` slug in the (final) frontmatter has
    `add_backlink` invoked for it. add_backlink is idempotent and a
    silent no-op when the entity profile doesn't yet exist, so the worst
    case is one stat() per slug per watcher event.
    """
    settings = load_settings()
    brain = settings.brain_dir.resolve()
    path = path.resolve()

    inferred_type, inferred_domain = _infer_type_and_domain(brain, path)
    if not inferred_type:
        # Not under signals/ or domains/X/ — outside our supplementation scope.
        return False

    try:
        post = frontmatter.load(path)
    except Exception:
        # Malformed frontmatter — rewrite from scratch below.
        post = frontmatter.Post(path.read_text(encoding="utf-8"))

    meta = dict(post.metadata or {})
    required = ("id", "type", "domain", "entities", "created_at", "source")
    rewritten = False
    if not all(k in meta for k in required):
        meta.setdefault("id", path.stem)
        meta.setdefault("type", inferred_type)
        # domain may legitimately be None for signals; setdefault is fine.
        if "domain" not in meta:
            meta["domain"] = inferred_domain
        meta.setdefault("entities", [])
        if "created_at" not in meta:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=KST)
            meta["created_at"] = mtime.isoformat()
        meta.setdefault("source", source)

        new_post = frontmatter.Post(post.content, **meta)
        path.write_text(frontmatter.dumps(new_post) + "\n", encoding="utf-8")
        rewritten = True

    _apply_entity_backlinks(path, meta.get("entities") or [])

    # Watcher-supplement path mirrors capture()'s fire-and-forget webhooks
    # so externally-dropped files get the same auto-extraction. We only
    # fire when something was actually rewritten — files whose required
    # fields were already complete came from capture() (which already
    # fired) or were edited in body only (no extraction signal change).
    if rewritten:
        _schedule_capture_event_webhooks(
            str(meta.get("id") or path.stem),
            path,
            str(meta.get("type") or inferred_type),
            (meta.get("domain") if meta.get("domain") is not None else None),
        )
    return rewritten


def capture_structured(
    template: str,
    fields: dict[str, object] | None = None,
    *,
    title: str | None = None,
    source: str = "typed",
) -> CaptureResult:
    """Capture a template-based record.

    - Loads `templates/<template>.md`.
    - Coerces raw string fields via TemplateField rules.
    - Builds frontmatter = {id, type, domain, template, <fields>, entities, created_at, source}.
    - Body = scaffold of ## headers from template.body_sections (user edits after).
    - Writes to brain/domains/<domain>/ (or brain/signals/ if domain unknown).
    - Entities field is auto-populated by scanning entity-ref(-list) field values.

    Returns the same CaptureResult shape as `capture()`.
    """
    # Late import avoids a circular dependency at module-load time
    # (templates.py imports DOMAINS from this module).
    from mcs.adapters.templates import (
        Template,
        TemplateError,
        assemble_body,
        coerce_field_value,
        load_template,
    )

    tpl: Template = load_template(template)
    fields = dict(fields or {})

    # Coerce + validate
    resolved: dict[str, object] = {}
    for f in tpl.fields:
        raw = fields.get(f.name)
        if raw is None:
            raw = ""
        # Accept already-list for entity-ref-list (coming from MCP JSON)
        if f.kind == "entity-ref-list" and isinstance(raw, list):
            resolved[f.name] = [str(x).strip() for x in raw if str(x).strip()]
            continue
        resolved[f.name] = coerce_field_value(f, str(raw))

    # Collect implied entities from entity-ref fields.
    entities: list[str] = []
    for f in tpl.fields:
        val = resolved.get(f.name)
        if f.kind == "entity-ref" and isinstance(val, str):
            entities.append(val)
        elif f.kind == "entity-ref-list" and isinstance(val, list):
            entities.extend(val)

    # Route to domain folder (fallback to signals if domain missing/unknown).
    domain_for_routing = tpl.domain if tpl.domain in DOMAINS else None

    settings = load_settings()
    brain = settings.brain_dir.resolve()
    now = now_kst()
    slug = generate_slug(now=now, title=title or template)

    meta = {
        "id": slug,
        "type": tpl.default_type or "note",
        "template": tpl.name,
        "domain": domain_for_routing,
        "entities": entities,
        "created_at": now.isoformat(),
        "source": source,
    }
    # Merge template field values, skipping None and the reserved keys.
    for k, v in resolved.items():
        if v is None:
            continue
        if k in meta:
            continue
        meta[k] = v

    folder = _target_folder(brain, domain_for_routing)
    folder.mkdir(parents=True, exist_ok=True)

    path = folder / f"{slug}.md"
    counter = 2
    base = path.with_suffix("")
    while path.exists():
        path = base.with_name(f"{base.name}-{counter}").with_suffix(".md")
        counter += 1

    meta["id"] = path.stem
    body = assemble_body(tpl)
    post = frontmatter.Post(body, **meta)
    path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")

    _apply_entity_backlinks(path, entities)

    result = CaptureResult(
        path=path,
        id=meta["id"],
        type=str(meta["type"]),
        domain=domain_for_routing,
    )
    _schedule_capture_event_webhooks(result.id, result.path, result.type, result.domain)
    return result


def capture(
    text: str,
    domain: str | None = None,
    entities: Iterable[str] | None = None,
    source: str = "typed",
    title: str | None = None,
    okrs: Iterable[str] | None = None,
) -> CaptureResult:
    """Capture a one-line memo to brain/.

    Args:
        text:     Memo body (free-form).
        domain:   One of DOMAINS, or None → signals/.
        entities: Entity slugs to link (list of `kind/slug`).
        source:   Where the capture came from. typed | chat | file-watcher | hermes-generated | auto-promoted.
        title:    Optional slug-friendly title (else auto-timestamp).
        okrs:     KR ids this memo relates to. Persisted as `okrs: [...]`
                  in frontmatter — a lightweight back-link so KRs can
                  surface their evidence captures later.

    Returns:
        CaptureResult with path and id.

    Raises:
        ValueError: domain not in DOMAINS.
    """
    if domain is not None and domain not in DOMAINS:
        raise ValueError(
            f"Unknown domain {domain!r}. Valid: {sorted(DOMAINS)}"
        )

    settings = load_settings()
    brain = settings.brain_dir.resolve()

    now = now_kst()
    slug = generate_slug(now=now, title=title)

    meta: dict[str, Any] = {
        "id": slug,
        "type": "note" if domain else "signal",
        "domain": domain,
        "entities": list(entities or []),
        "created_at": now.isoformat(),
        "source": source,
    }
    okr_list = [s.strip() for s in (okrs or []) if s and s.strip()]
    if okr_list:
        meta["okrs"] = okr_list

    folder = _target_folder(brain, domain)
    folder.mkdir(parents=True, exist_ok=True)

    path = folder / f"{slug}.md"
    # 충돌 방지: 같은 slug 파일이 이미 있으면 suffix
    counter = 2
    base = path.with_suffix("")
    while path.exists():
        path = base.with_name(f"{base.name}-{counter}").with_suffix(".md")
        counter += 1

    # 파일명과 frontmatter id 정합성 보장
    meta["id"] = path.stem

    post = frontmatter.Post(text.rstrip() + "\n", **meta)
    path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")

    _apply_entity_backlinks(path, meta["entities"])

    result = CaptureResult(path=path, id=meta["id"], type=meta["type"], domain=domain)
    _schedule_capture_event_webhooks(result.id, result.path, result.type, result.domain)
    return result


def _apply_entity_backlinks(record_path: Path, entity_slugs: Iterable[str]) -> None:
    """Wire FR-C3 manual back-links from a freshly written record.

    Late-imported to break the entity↔memory module cycle. Silent no-op
    for any slug whose profile doesn't exist yet — keeps `mcs capture -e
    people/jane` working before the user has approved Jane's draft.
    """
    slugs = [s for s in (entity_slugs or []) if s]
    if not slugs:
        return
    from mcs.adapters import entity as entity_mod

    for slug in slugs:
        try:
            entity_mod.add_backlink(slug, record_path)
        except entity_mod.EntityError:
            continue


def _schedule_capture_event_webhooks(
    capture_id: str,
    capture_path: Path,
    capture_type: str,
    domain: str | None,
) -> None:
    """Fan out fire-and-forget webhook POSTs to every enabled extractor.

    Currently entity-extract (FR-C1) and domain-classify (FR-A3). Each
    fires only when its own enable flag + secret are set. Both share
    the same payload shape so future extractors can subscribe to a
    sibling route without changing this dispatch.

    Skipped wholesale when no asyncio loop is running (CLI direct path).
    Failures are logged at most — never raised back into the caller.
    """
    settings = load_settings()

    routes: list[tuple[str, str, str]] = []  # (label, route, secret)
    if settings.entity_extract_webhook_enabled and settings.entity_extract_webhook_secret:
        routes.append((
            "entity-extract",
            settings.entity_extract_webhook_route,
            settings.entity_extract_webhook_secret,
        ))
    if settings.domain_classify_webhook_enabled and settings.domain_classify_webhook_secret:
        routes.append((
            "domain-classify",
            settings.domain_classify_webhook_route,
            settings.domain_classify_webhook_secret,
        ))
    if not routes:
        return

    import asyncio as _asyncio  # local alias keeps memory.py top imports clean
    in_thread = False
    try:
        loop = _asyncio.get_running_loop()
    except RuntimeError:
        # No loop in this thread — try the watcher-bound server loop. This
        # is the path the watchdog observer thread takes when it calls
        # supplement_frontmatter on a freshly dropped file.
        from mcs.adapters.watcher import get_main_loop
        loop = get_main_loop()
        if loop is None or loop.is_closed():
            return
        in_thread = True

    payload = {
        "capture_id": capture_id,
        "capture_path": str(capture_path),
        "type": capture_type,
        "domain": domain,
    }

    async def _fire(label: str, route: str, secret: str) -> None:
        from mcs.adapters.hermes_client import fire_webhook
        out = await fire_webhook(route, payload, secret=secret)
        if not out["ok"]:
            print(
                f"[{label} webhook] {route} failed: {out['error']}",
                flush=True,
            )

    for label, route, secret in routes:
        coro = _fire(label, route, secret)
        if in_thread:
            _asyncio.run_coroutine_threadsafe(coro, loop)
        else:
            loop.create_task(coro)


