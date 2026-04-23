"""OKR adapter — brain/objectives/ is the SSoT.

Layout:
  brain/objectives/{quarter}/{slug}/
    _objective.md           (type=objective)
    kr-1-{slug}.md          (type=kr, parent=<objective id>)
    kr-2-{slug}.md
    ...

Contract:
  - magic-conch-shell writes OKRs (planner role).
  - plan-tracker reads them and keeps its own weekly snapshots.
  - The `current` / `status` fields here are the initial/planning
    state. Live progress comes from plan-tracker via MCP.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import frontmatter

from mcs.adapters.memory import DOMAINS, _kebab
from mcs.config import load_settings


KST = ZoneInfo("Asia/Seoul")


# ─── Valid enum domains ─────────────────────────────────────────────────

_OBJECTIVE_STATUSES = frozenset({"active", "paused", "achieved", "abandoned"})
_KR_STATUSES = frozenset({"pending", "in_progress", "achieved", "missed", "abandoned"})
_KR_UNITS = frozenset({"count", "percent", "currency", "binary"})

# When an Objective closes, its remaining KRs cascade to a matching terminal state.
# paused is not a close — KRs stay as-is.
_OBJECTIVE_TO_KR_CASCADE = {
    "achieved": "achieved",
    "abandoned": "abandoned",
}
_TERMINAL_KR_STATUSES = frozenset({"achieved", "missed", "abandoned"})


# ─── Errors ─────────────────────────────────────────────────────────────

class OKRError(ValueError):
    """Schema / validation / lookup failure."""


class OKRNotFound(LookupError):
    """No Objective or KR matches the lookup."""


# ─── Dataclasses ────────────────────────────────────────────────────────

@dataclass
class KeyResult:
    id: str
    parent: str
    text: str
    target: float
    current: float
    unit: str
    status: str
    due: str | None
    created_at: str
    updated_at: str
    path: Path
    body: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent": self.parent,
            "text": self.text,
            "target": self.target,
            "current": self.current,
            "unit": self.unit,
            "status": self.status,
            "due": self.due,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "path": str(self.path),
            "body": self.body,
        }


@dataclass
class Objective:
    id: str
    quarter: str
    domain: str
    status: str
    confidence: float
    created_at: str
    updated_at: str
    entities: list[str]
    path: Path                    # path to _objective.md
    folder: Path                  # containing folder
    body: str = ""
    krs: list[KeyResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "quarter": self.quarter,
            "domain": self.domain,
            "status": self.status,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "entities": self.entities,
            "path": str(self.path),
            "folder": str(self.folder),
            "body": self.body,
            "krs": [kr.to_dict() for kr in self.krs],
        }


# ─── Helpers ────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(KST).isoformat()


def _objectives_root() -> Path:
    return load_settings().brain_dir.resolve() / "objectives"


def _validate_quarter(q: str) -> None:
    if not re.fullmatch(r"\d{4}-Q[1-4]", q):
        raise OKRError(f"quarter {q!r} must match 'YYYY-Q[1-4]'")


def _objective_id(quarter: str, slug: str) -> str:
    _validate_quarter(quarter)
    return f"{quarter}-{slug}"


def _parse_id(objective_id: str) -> tuple[str, str]:
    """Split '2026-Q2-career-mle-role' → ('2026-Q2', 'career-mle-role')."""
    m = re.match(r"^(\d{4}-Q[1-4])-(.+)$", objective_id)
    if not m:
        raise OKRError(f"objective id {objective_id!r} malformed")
    return m.group(1), m.group(2)


def _kr_id(parent_id: str, n: int) -> str:
    return f"{parent_id}.kr-{n}"


def _kr_filename(n: int, text: str) -> str:
    """kr-1-anthropic-1st-interview.md"""
    slug = _kebab(text, max_len=40) or f"kr-{n}"
    return f"kr-{n}-{slug}.md"


def _next_kr_number(folder: Path) -> int:
    nums = []
    for p in folder.glob("kr-*.md"):
        m = re.match(r"^kr-(\d+)-", p.name)
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def _assert_valid_domain(domain: str) -> None:
    if domain not in DOMAINS:
        raise OKRError(f"domain {domain!r} not in {sorted(DOMAINS)}")


def _assert_valid_objective_status(status: str) -> None:
    if status not in _OBJECTIVE_STATUSES:
        raise OKRError(
            f"objective status {status!r} must be one of {sorted(_OBJECTIVE_STATUSES)}"
        )


def _assert_valid_kr_status(status: str) -> None:
    if status not in _KR_STATUSES:
        raise OKRError(
            f"kr status {status!r} must be one of {sorted(_KR_STATUSES)}"
        )


def _assert_valid_kr_unit(unit: str) -> None:
    if unit not in _KR_UNITS:
        raise OKRError(f"kr unit {unit!r} must be one of {sorted(_KR_UNITS)}")


# ─── Load ───────────────────────────────────────────────────────────────

def _load_objective_file(path: Path) -> Objective:
    post = frontmatter.load(path)
    meta = post.metadata or {}
    folder = path.parent
    obj = Objective(
        id=str(meta.get("id") or ""),
        quarter=str(meta.get("quarter") or ""),
        domain=str(meta.get("domain") or ""),
        status=str(meta.get("status") or "active"),
        confidence=float(meta.get("confidence") or 0.0),
        created_at=str(meta.get("created_at") or ""),
        updated_at=str(meta.get("updated_at") or ""),
        entities=list(meta.get("entities") or []),
        path=path.resolve(),
        folder=folder.resolve(),
        body=(post.content or "").strip(),
        krs=[],
    )
    for kr_path in sorted(folder.glob("kr-*.md")):
        obj.krs.append(_load_kr_file(kr_path))
    return obj


def _load_kr_file(path: Path) -> KeyResult:
    post = frontmatter.load(path)
    meta = post.metadata or {}
    return KeyResult(
        id=str(meta.get("id") or ""),
        parent=str(meta.get("parent") or ""),
        text=str(meta.get("text") or ""),
        target=float(meta.get("target") or 0),
        current=float(meta.get("current") or 0),
        unit=str(meta.get("unit") or "count"),
        status=str(meta.get("status") or "pending"),
        due=(str(meta["due"]) if "due" in meta and meta["due"] is not None else None),
        created_at=str(meta.get("created_at") or ""),
        updated_at=str(meta.get("updated_at") or ""),
        path=path.resolve(),
        body=(post.content or "").strip(),
    )


def _find_objective_path(objective_id: str) -> Path:
    quarter, slug = _parse_id(objective_id)
    p = _objectives_root() / quarter / slug / "_objective.md"
    if not p.exists():
        raise OKRNotFound(f"objective {objective_id!r} not found at {p}")
    return p.resolve()


def _find_kr_path(kr_id: str) -> Path:
    # '2026-Q2-career-mle-role.kr-3' → parent + number
    if ".kr-" not in kr_id:
        raise OKRError(f"kr id {kr_id!r} malformed")
    parent_id, suffix = kr_id.split(".kr-", 1)
    try:
        n = int(suffix)
    except ValueError:
        raise OKRError(f"kr id {kr_id!r} has non-numeric suffix {suffix!r}")
    quarter, slug = _parse_id(parent_id)
    folder = _objectives_root() / quarter / slug
    matches = list(folder.glob(f"kr-{n}-*.md"))
    if not matches:
        raise OKRNotFound(f"kr {kr_id!r} not found in {folder}")
    if len(matches) > 1:
        raise OKRError(
            f"kr {kr_id!r} matches multiple files: {[p.name for p in matches]}"
        )
    return matches[0].resolve()


# ─── Public API — read ─────────────────────────────────────────────────

_DEFAULT_LIST_STATUSES = frozenset({"active"})


def current_quarter(now: datetime | None = None) -> str:
    """KST-today's quarter as 'YYYY-Q[1-4]'."""
    n = now or datetime.now(KST)
    q = (n.month - 1) // 3 + 1
    return f"{n.year}-Q{q}"


def list_active(
    quarter: str | None = None,
    *,
    statuses: Iterable[str] | None = None,
    domain: str | None = None,
) -> list[Objective]:
    """Scan brain/objectives/ and return matching Objectives.

    Default: status = {active} (hides achieved/paused/abandoned so
    `list` shows only what's currently in motion).
    Pass `statuses={"all"}` to include every status, or an explicit
    subset (e.g. {"achieved"}) to filter precisely.
    `domain` filters to a single domain; omit for all.
    """
    root = _objectives_root()
    if not root.exists():
        return []

    allowed = (
        _DEFAULT_LIST_STATUSES if statuses is None else frozenset(statuses)
    )
    include_all = "all" in allowed

    quarters: Iterable[Path]
    if quarter:
        _validate_quarter(quarter)
        quarters = [root / quarter] if (root / quarter).exists() else []
    else:
        quarters = sorted(p for p in root.iterdir() if p.is_dir())

    out: list[Objective] = []
    for qdir in quarters:
        for slug_dir in sorted(p for p in qdir.iterdir() if p.is_dir()):
            obj_file = slug_dir / "_objective.md"
            if not obj_file.exists():
                continue
            obj = _load_objective_file(obj_file)
            if not include_all and obj.status not in allowed:
                continue
            if domain is not None and obj.domain != domain:
                continue
            out.append(obj)
    return out


def get(objective_id: str) -> Objective:
    return _load_objective_file(_find_objective_path(objective_id))


def get_kr(kr_id: str) -> KeyResult:
    return _load_kr_file(_find_kr_path(kr_id))


# ─── Public API — write ────────────────────────────────────────────────

def create_objective(
    *,
    slug: str,
    quarter: str,
    domain: str,
    confidence: float = 0.5,
    entities: list[str] | None = None,
    body: str = "",
) -> Objective:
    """Create a new Objective folder + _objective.md.

    Raises OKRError if the slug already exists in this quarter.
    """
    _validate_quarter(quarter)
    _assert_valid_domain(domain)
    slug = _kebab(slug, max_len=60) or slug
    folder = _objectives_root() / quarter / slug
    if folder.exists():
        raise OKRError(f"objective slug {slug!r} already exists in {quarter}")

    folder.mkdir(parents=True)
    obj_id = _objective_id(quarter, slug)
    now = _now()
    meta = {
        "id": obj_id,
        "type": "objective",
        "quarter": quarter,
        "domain": domain,
        "status": "active",
        "confidence": float(confidence),
        "created_at": now,
        "updated_at": now,
        "entities": list(entities or []),
    }
    path = folder / "_objective.md"
    path.write_text(
        frontmatter.dumps(frontmatter.Post(body or "", **meta)) + "\n",
        encoding="utf-8",
    )
    return _load_objective_file(path)


def create_kr(
    parent_id: str,
    *,
    text: str,
    target: float = 1.0,
    current: float = 0.0,
    unit: str = "count",
    status: str = "pending",
    due: str | None = None,
    body: str = "",
) -> KeyResult:
    """Create a new KR file under an existing objective folder."""
    _assert_valid_kr_status(status)
    _assert_valid_kr_unit(unit)

    obj_path = _find_objective_path(parent_id)
    folder = obj_path.parent
    n = _next_kr_number(folder)
    kr_id = _kr_id(parent_id, n)
    filename = _kr_filename(n, text)
    path = folder / filename

    now = _now()
    meta = {
        "id": kr_id,
        "type": "kr",
        "parent": parent_id,
        "text": text,
        "target": float(target),
        "current": float(current),
        "unit": unit,
        "status": status,
        "due": due,
        "created_at": now,
        "updated_at": now,
    }
    path.write_text(
        frontmatter.dumps(frontmatter.Post(body or "", **meta)) + "\n",
        encoding="utf-8",
    )
    _touch_parent(obj_path)
    return _load_kr_file(path)


def update_kr(kr_id: str, **fields: Any) -> KeyResult:
    """Patch a KR's frontmatter fields and re-stamp updated_at.

    Accepted fields: text, target, current, unit, status, due, body.

    When the caller does NOT set `status` explicitly, the KR's status
    auto-transitions based on current/target:
      - current >= target > 0     → achieved
      - current > 0, was pending  → in_progress
    Terminal statuses (achieved / missed / abandoned) are never
    regressed — if a user wants to reopen a terminal KR they must
    pass `status=...` explicitly.
    """
    path = _find_kr_path(kr_id)
    post = frontmatter.load(path)
    meta = dict(post.metadata or {})

    allowed = {"text", "target", "current", "unit", "status", "due"}
    for k, v in fields.items():
        if k == "body":
            continue
        if k not in allowed:
            raise OKRError(f"unknown kr field {k!r} (allowed: {sorted(allowed)})")
        if k == "status":
            _assert_valid_kr_status(str(v))
        if k == "unit":
            _assert_valid_kr_unit(str(v))
        if k in ("target", "current"):
            v = float(v)
        meta[k] = v

    # Auto-transition status based on progress when caller didn't override it.
    if "status" not in fields:
        status = str(meta.get("status") or "pending")
        if status not in _TERMINAL_KR_STATUSES:
            current_v = float(meta.get("current") or 0)
            target_v = float(meta.get("target") or 0)
            if target_v > 0 and current_v >= target_v:
                meta["status"] = "achieved"
            elif current_v > 0 and status == "pending":
                meta["status"] = "in_progress"

    meta["updated_at"] = _now()

    new_body = fields.get("body")
    body = new_body if new_body is not None else (post.content or "")
    path.write_text(
        frontmatter.dumps(frontmatter.Post(body, **meta)) + "\n",
        encoding="utf-8",
    )
    _touch_parent_by_kr(kr_id)
    return _load_kr_file(path)


def update_objective(objective_id: str, **fields: Any) -> Objective:
    """Patch an objective's top-level fields.

    When status transitions to `achieved` or `abandoned`, every KR still in
    a non-terminal state (pending / in_progress) is cascaded to the matching
    terminal status so kr-list and future reports stay consistent with the
    Objective's closure. `paused` does NOT cascade — pauses are temporary.
    """
    path = _find_objective_path(objective_id)
    post = frontmatter.load(path)
    meta = dict(post.metadata or {})
    prev_status = str(meta.get("status") or "active")

    allowed = {"status", "confidence", "domain", "entities"}
    for k, v in fields.items():
        if k == "body":
            continue
        if k not in allowed:
            raise OKRError(
                f"unknown objective field {k!r} (allowed: {sorted(allowed)})"
            )
        if k == "status":
            _assert_valid_objective_status(str(v))
        if k == "domain":
            _assert_valid_domain(str(v))
        if k == "confidence":
            v = float(v)
        meta[k] = v

    meta["updated_at"] = _now()
    new_body = fields.get("body")
    body = new_body if new_body is not None else (post.content or "")
    path.write_text(
        frontmatter.dumps(frontmatter.Post(body, **meta)) + "\n",
        encoding="utf-8",
    )

    # Cascade close → KR terminal state, only on status transitions we map.
    new_status = str(meta.get("status") or "active")
    cascade_to = _OBJECTIVE_TO_KR_CASCADE.get(new_status)
    if cascade_to and new_status != prev_status:
        _cascade_kr_status(path.parent, cascade_to)

    return _load_objective_file(path)


def _cascade_kr_status(folder: Path, target_status: str) -> None:
    """Set each non-terminal KR under `folder` to `target_status`."""
    for kr_path in sorted(folder.glob("kr-*.md")):
        post = frontmatter.load(kr_path)
        meta = dict(post.metadata or {})
        current = str(meta.get("status") or "pending")
        if current in _TERMINAL_KR_STATUSES:
            continue  # don't overwrite already-decided KRs
        meta["status"] = target_status
        meta["updated_at"] = _now()
        kr_path.write_text(
            frontmatter.dumps(frontmatter.Post(post.content or "", **meta)) + "\n",
            encoding="utf-8",
        )


def _touch_parent(obj_path: Path) -> None:
    """Stamp parent objective's updated_at when a child changes."""
    post = frontmatter.load(obj_path)
    meta = dict(post.metadata or {})
    meta["updated_at"] = _now()
    obj_path.write_text(
        frontmatter.dumps(frontmatter.Post(post.content or "", **meta)) + "\n",
        encoding="utf-8",
    )


def _touch_parent_by_kr(kr_id: str) -> None:
    parent_id = kr_id.split(".kr-", 1)[0]
    try:
        _touch_parent(_find_objective_path(parent_id))
    except OKRNotFound:
        pass


# ─── KR agent spawn / find ──────────────────────────────────────────────

def _agent_dir_name(kr_id: str) -> str:
    """`2026-Q2-career-mle-role.kr-1` → `2026-Q2-career-mle-role-kr-1`."""
    return kr_id.replace(".", "-")


def _skills_objectives_root() -> Path:
    return load_settings().repo_root.resolve() / "skills" / "objectives"


_KR_AGENT_SKILL_TEMPLATE = """\
---
name: {slug}
description: |
  Working agent for KR "{kr_text}" under Objective {parent_id}.
  Invoke via /{slug}. Loads the current KR state, surfaces linked
  captures, and helps the user push progress forward.
metadata:
  hermes:
    tags: [objectives, kr-agent]
    requires_tools:
      - mcp_mcs_okr_get_kr
      - mcp_mcs_okr_update_kr
      - mcp_mcs_memory_search
      - mcp_mcs_memory_capture
  mcs:
    kr_id: {kr_id}
    parent_objective: {parent_id}
    created_at: {created_at}
---

# {kr_text}

## 역할
이 KR 전용 작업 보조. 세션 시작 때:

1. `mcp_mcs_okr_get_kr(kr_id="{kr_id}")` 로 현재 상태 (current/target/status/due) 로드
2. 필요 시 `mcp_mcs_memory_search` 로 이 KR 에 링크된 메모 조회
3. 사용자 요청에 맞춰 작업 지원 (계획 제안·진척 기록·관련 메모 캡처)

진척이 생기면 `mcp_mcs_okr_update_kr` 로 current 증가. 새 관찰/결정은
`mcp_mcs_memory_capture` 로 `okrs=["{kr_id}"]` 링크해서 저장.

## KR 목표
- **Text**: {kr_text}
- **Target**: {target} {unit}
- **Due**: {due_str}
- **Parent Objective**: {parent_id}

## Acceptance Criteria
{acceptance_block}

## 작업 원칙
- 짧게 대화 (SOUL.md consulting 톤).
- 이 KR 과 무관한 주제로 샛길 가지 말기.
- 달성 직전 (current == target) 되면 사용자에게 "close 할까?" 물어보기.

## 진척 기록
(신규 진척 발생 시 날짜 + 한 줄 요약 아래에 append)

"""


def spawn_kr_agent(
    kr_id: str,
    *,
    acceptance_criteria: list[str] | None = None,
    overwrite: bool = False,
) -> Path:
    """Create `skills/objectives/<dashed-kr-id>/SKILL.md` for a KR.

    Idempotent: if the agent folder already exists, raises unless
    `overwrite=True`. Loads the KR + parent Objective to populate
    the template. Returns the SKILL.md path.
    """
    kr = get_kr(kr_id)  # raises OKRNotFound if missing
    parent_id = kr.parent
    slug = _agent_dir_name(kr_id)
    folder = _skills_objectives_root() / slug
    skill_path = folder / "SKILL.md"

    if skill_path.exists() and not overwrite:
        raise OKRError(
            f"agent for {kr_id!r} already exists at {skill_path} "
            f"(pass overwrite=True to replace)"
        )

    crit_lines = acceptance_criteria or ["TODO: 첫 번째 인수 조건"]
    acceptance_block = "\n".join(f"- [ ] {line}" for line in crit_lines)
    due_str = kr.due or "TBD"

    folder.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(
        _KR_AGENT_SKILL_TEMPLATE.format(
            slug=slug,
            kr_id=kr_id,
            kr_text=kr.text,
            target=_fmt_num(kr.target),
            unit=kr.unit,
            due_str=due_str,
            parent_id=parent_id,
            acceptance_block=acceptance_block,
            created_at=_now(),
        ),
        encoding="utf-8",
    )
    return skill_path


def find_kr_agent(kr_id: str) -> Path | None:
    """Return the SKILL.md path for a KR agent, or None if not spawned."""
    root = _skills_objectives_root()
    if not root.exists():
        return None
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        skill = folder / "SKILL.md"
        if not skill.exists():
            continue
        try:
            post = frontmatter.load(skill)
        except Exception:
            continue
        meta = post.metadata or {}
        mcs_block = meta.get("metadata", {}).get("mcs") if isinstance(
            meta.get("metadata"), dict
        ) else None
        # Support both nested and flat mcs block locations.
        ref = (mcs_block or meta.get("mcs") or {})
        if isinstance(ref, dict) and ref.get("kr_id") == kr_id:
            return skill.resolve()
    return None


def _fmt_num(n: float) -> str:
    """Render floats without trailing .0 when they're whole."""
    return f"{n:g}"
