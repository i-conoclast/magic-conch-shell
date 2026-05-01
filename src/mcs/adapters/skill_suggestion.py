"""Skill-promotion drafts (FR-E5).

Stores user- or detector-proposed skill drafts under
`.brain/skill-suggestions/<slug>.md`. The inbox aggregator (FR-G3)
surfaces them; `inbox-approve` confirms them by moving the draft to
`skills/<target_dir>/<slug>/SKILL.md`.

The detection side (auto-recognizing repeated patterns) is deferred to
v1 — for now the only producer is `mcs skill propose` which creates
drafts manually so the pipeline can be exercised and reviewed in
evening retro alongside entity drafts.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter

from mcs.adapters.memory import _kebab, now_kst
from mcs.config import load_settings


# ─── errors ────────────────────────────────────────────────────────────

class SkillSuggestionError(Exception):
    """Base class for skill_suggestion errors."""


class SuggestionNotFound(SkillSuggestionError):
    """No draft matches the given slug."""


class SuggestionAlreadyExists(SkillSuggestionError):
    """A draft (or a same-named active skill) already exists."""


# ─── data ──────────────────────────────────────────────────────────────

@dataclass
class SkillSuggestion:
    """One pending skill-promotion draft."""

    slug: str
    name: str
    detected_at: str
    path: Path
    source_session_id: str | None = None
    summary: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "detected_at": self.detected_at,
            "path": str(self.path),
            "source_session_id": self.source_session_id,
            "summary": self.summary,
            "meta": self.meta,
        }


# ─── path helpers ──────────────────────────────────────────────────────

def _suggestions_root() -> Path:
    return load_settings().cache_dir.resolve() / "skill-suggestions"


def _draft_path(slug: str) -> Path:
    return _suggestions_root() / f"{slug}.md"


def _slug_from_name(name: str) -> str:
    slug = _kebab(name)
    if not slug:
        raise ValueError(f"cannot derive slug from name {name!r}")
    return slug


_SAFE_TARGET_DIR = re.compile(r"^[a-z][a-z0-9_-]*$")


# ─── lookup / list ─────────────────────────────────────────────────────

def _load_suggestion(path: Path) -> SkillSuggestion:
    post = frontmatter.load(path)
    meta = dict(post.metadata or {})
    return SkillSuggestion(
        slug=str(meta.get("slug") or path.stem),
        name=str(meta.get("name") or path.stem),
        detected_at=str(meta.get("detected_at") or ""),
        path=path.resolve(),
        source_session_id=(
            str(meta["source_session_id"]) if "source_session_id" in meta else None
        ),
        summary=str(meta.get("summary") or ""),
        meta=meta,
    )


def resolve(slug: str) -> SkillSuggestion:
    p = _draft_path(slug)
    if not p.exists():
        raise SuggestionNotFound(f"no skill suggestion at slug {slug!r}")
    return _load_suggestion(p)


def list_drafts() -> list[SkillSuggestion]:
    root = _suggestions_root()
    if not root.exists():
        return []
    return sorted(
        (_load_suggestion(p) for p in root.glob("*.md")),
        key=lambda s: s.detected_at,
        reverse=True,
    )


# ─── create ────────────────────────────────────────────────────────────

def create_draft(
    slug: str | None = None,
    *,
    name: str,
    body: str = "",
    source_session_id: str | None = None,
    summary: str = "",
    extra: dict[str, Any] | None = None,
) -> SkillSuggestion:
    """Stage a skill-promotion draft.

    Refuses when a same-slug draft already exists (idempotent semantics
    are too easy to abuse here — use the CLI `--force` if you really
    want to overwrite). Also refuses when an active skill at
    `skills/planner/<slug>/SKILL.md` is already present, since that's
    the eventual target of confirm().
    """
    final_slug = slug or _slug_from_name(name)

    suggestions = _suggestions_root()
    suggestions.mkdir(parents=True, exist_ok=True)

    target = _draft_path(final_slug)
    if target.exists():
        raise SuggestionAlreadyExists(
            f"draft already at {target.relative_to(load_settings().cache_dir)}"
        )

    # Refuse if an active skill of the same slug is already deployed —
    # we don't want users to "promote" something into an existing skill.
    settings = load_settings()
    repo = settings.repo_root.resolve()
    for parent in ("skills/planner", "skills/extractor", "skills/objectives"):
        if (repo / parent / final_slug / "SKILL.md").exists():
            raise SuggestionAlreadyExists(
                f"active skill already at {parent}/{final_slug}/SKILL.md"
            )

    meta: dict[str, Any] = {
        "slug": final_slug,
        "name": name,
        "detected_at": now_kst().isoformat(),
        "status": "draft",
    }
    if source_session_id:
        meta["source_session_id"] = source_session_id
    if summary:
        meta["summary"] = summary
    if extra:
        for k, v in extra.items():
            if k in meta or v is None:
                continue
            meta[k] = v

    if not body:
        body = (
            "# " + name + "\n\n"
            "_(promotion draft — edit before approving)_\n\n"
            "## 트리거\n\n"
            "## 당신의 역할\n\n"
            "## 대화 흐름\n\n"
            "## 사용 가능한 MCP 도구\n"
        )

    target.write_text(
        frontmatter.dumps(frontmatter.Post(body, **meta)) + "\n",
        encoding="utf-8",
    )
    return _load_suggestion(target)


# ─── confirm / reject ─────────────────────────────────────────────────

def confirm(slug: str, *, target_dir: str = "planner") -> dict[str, Any]:
    """Promote a draft to `skills/<target_dir>/<slug>/SKILL.md`.

    Strips lifecycle frontmatter (`status`, `detected_at`,
    `source_session_id`) and writes the cleaned post under skills/.
    Refuses when the destination already exists.
    """
    if not _SAFE_TARGET_DIR.match(target_dir):
        raise SkillSuggestionError(
            f"invalid target_dir {target_dir!r} — use a simple slug like "
            f"'planner' or 'extractor'."
        )

    sug = resolve(slug)
    settings = load_settings()
    repo = settings.repo_root.resolve()
    dest = repo / "skills" / target_dir / sug.slug / "SKILL.md"
    if dest.exists():
        raise SuggestionAlreadyExists(
            f"target already exists at {dest.relative_to(repo)}"
        )

    post = frontmatter.load(sug.path)
    meta = dict(post.metadata or {})
    for k in ("status", "detected_at", "source_session_id", "summary"):
        meta.pop(k, None)
    meta.setdefault("name", sug.name)

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        frontmatter.dumps(frontmatter.Post(post.content or "", **meta)) + "\n",
        encoding="utf-8",
    )
    sug.path.unlink()

    return {
        "slug": sug.slug,
        "status": "confirmed",
        "path": str(dest),
        "target_dir": target_dir,
    }


def reject(slug: str, *, reason: str | None = None) -> dict[str, Any]:
    """Delete a draft and append a JSONL rejection record."""
    sug = resolve(slug)
    settings = load_settings()
    log_path = settings.cache_dir.resolve() / "rejected-skill-suggestions.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "slug": sug.slug,
        "name": sug.name,
        "rejected_at": now_kst().isoformat(),
        "reason": reason,
    }
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    sug.path.unlink()
    return {"slug": sug.slug, "status": "rejected", "reason": reason}


__all__ = [
    "SkillSuggestion",
    "SkillSuggestionError",
    "SuggestionAlreadyExists",
    "SuggestionNotFound",
    "confirm",
    "create_draft",
    "list_drafts",
    "reject",
    "resolve",
]
