"""Memory operations — capture, search, entities.

SSoT is `brain/` markdown files with YAML frontmatter.
Cache (`.brain/`) is rebuildable at any time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
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


def capture(
    text: str,
    domain: str | None = None,
    entities: Iterable[str] | None = None,
    source: str = "typed",
    title: str | None = None,
) -> CaptureResult:
    """Capture a one-line memo to brain/.

    Args:
        text:     Memo body (free-form).
        domain:   One of DOMAINS, or None → signals/.
        entities: Entity slugs to link (list of `kind/slug`).
        source:   Where the capture came from. typed | chat | file-watcher | hermes-generated | auto-promoted.
        title:    Optional slug-friendly title (else auto-timestamp).

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

    meta = {
        "id": slug,
        "type": "note" if domain else "signal",
        "domain": domain,
        "entities": list(entities or []),
        "created_at": now.isoformat(),
        "source": source,
    }

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

    return CaptureResult(path=path, id=meta["id"], type=meta["type"], domain=domain)
