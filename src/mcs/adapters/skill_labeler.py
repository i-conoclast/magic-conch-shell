"""LLM labeling for FR-E5 skill candidates (Phase 12.3).

Bridges `skill_detector.SkillCandidate` to a persisted
`skill_suggestion` draft by calling the Hermes `skill-name-suggest`
skill once per candidate. The skill is expected to return a single
JSON object with `slug / name / summary / body` (or `slug: null` for
"this cluster isn't worth a skill").

Per the Hermes-owns-LLM rule (`feedback_hermes_owns_llm` memory), this
module never embeds prompt logic — the prompt body lives in the
SKILL.md and only the inputs are formatted here.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable

from mcs.adapters import skill_suggestion as ss
from mcs.adapters.hermes_client import run_skill
from mcs.adapters.skill_detector import SkillCandidate


# ─── data ──────────────────────────────────────────────────────────────

@dataclass
class LabeledCandidate:
    """Result of labeling one candidate. Either a draft was created,
    the LLM said the cluster wasn't worth promoting, or something failed.
    """

    candidate_seed_id: str
    status: str          # "created" | "skipped-by-llm" | "skipped-existing" | "error"
    slug: str | None = None
    reason: str | None = None
    draft_path: str | None = None
    raw_response: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_seed_id": self.candidate_seed_id,
            "status": self.status,
            "slug": self.slug,
            "reason": self.reason,
            "draft_path": self.draft_path,
        }


# ─── prompt formatting ─────────────────────────────────────────────────

def format_candidate_opener(candidate: SkillCandidate) -> str:
    """Build the opener string the SKILL.md expects.

    Lives here (not in the SKILL.md) because the data shape is mcs's,
    not Hermes's. The SKILL.md tells the LLM how to read this format;
    this function produces it.
    """
    domains = candidate.payload.get("domains") or []
    domain_str = ", ".join(domains) if domains else ""
    sample_lines = []
    for i, text in enumerate(candidate.sample_texts, start=1):
        single = " ".join(text.split())  # collapse newlines/runs
        sample_lines.append(f"  {i}. {single}")

    return (
        f"cluster_seed: {candidate.seed_id}\n"
        f"member_count: {len(candidate.member_ids)}\n"
        f"time_spread_days: {candidate.time_spread_days:.2f}\n"
        f"avg_score: {candidate.avg_score:.3f}\n"
        f"domains: [{domain_str}]\n"
        f"sample_excerpts:\n"
        + "\n".join(sample_lines)
    )


# ─── response parsing ──────────────────────────────────────────────────

_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def parse_label_response(text: str) -> dict[str, Any]:
    """Extract the JSON object the SKILL.md is supposed to produce.

    Lenient: strips leading prose / trailing commentary if the model
    leaks them, and unwraps fenced ```json``` blocks. Raises ValueError
    on irrecoverable output.
    """
    if not text:
        raise ValueError("empty response from labeling skill")

    # Try fenced block first.
    m = _JSON_FENCE.search(text)
    raw = m.group(1) if m else None
    if raw is None:
        m = _JSON_OBJECT.search(text)
        raw = m.group(0) if m else None
    if raw is None:
        raise ValueError(f"no JSON object found in response: {text[:200]!r}")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"could not parse JSON: {e}; raw: {raw[:200]!r}") from e


# ─── orchestration ─────────────────────────────────────────────────────

# Injectable so tests can run without Hermes.
RunSkillFn = Callable[..., Awaitable[dict[str, Any]]]


def _session_name(seed_id: str, *, now: datetime | None = None) -> str:
    """Per-cluster, per-day session name.

    Re-running the labeler on the same cluster the same day resumes
    the conversation; next-day runs start fresh. Keeps Hermes's
    response_store from inflating with one-off labelings.
    """
    n = now or datetime.now()
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", seed_id)[:40]
    return f"skill-name-suggest-{n.strftime('%Y-%m-%d')}-{safe}"


async def _default_run(
    *, skill: str, opener: str, conversation: str, timeout: float
) -> dict[str, Any]:
    return await run_skill(
        skill=skill, opener=opener, conversation=conversation, timeout=timeout
    )


async def label_candidate(
    candidate: SkillCandidate,
    *,
    timeout: float = 90.0,
    run_fn: RunSkillFn | None = None,
) -> LabeledCandidate:
    """Run the labeling skill once and persist the draft if accepted."""
    runner = run_fn or _default_run
    opener = format_candidate_opener(candidate)
    session = _session_name(candidate.seed_id)

    try:
        result = await runner(
            skill="skill-name-suggest",
            opener=opener,
            conversation=session,
            timeout=timeout,
        )
    except Exception as e:
        return LabeledCandidate(
            candidate_seed_id=candidate.seed_id,
            status="error",
            reason=f"labeling skill failed: {e}",
        )

    text = (result.get("text") or "").strip()
    try:
        parsed = parse_label_response(text)
    except ValueError as e:
        return LabeledCandidate(
            candidate_seed_id=candidate.seed_id,
            status="error",
            reason=str(e),
            raw_response=text,
        )

    slug = parsed.get("slug")
    if not slug:
        return LabeledCandidate(
            candidate_seed_id=candidate.seed_id,
            status="skipped-by-llm",
            reason=str(parsed.get("reason") or "llm declined to label"),
            raw_response=text,
        )

    name = str(parsed.get("name") or slug.replace("-", " ").title())
    summary = str(parsed.get("summary") or "")
    body = str(parsed.get("body") or "")

    try:
        sug = ss.create_draft(
            slug=str(slug),
            name=name,
            body=body,
            summary=summary,
            source_session_id=f"skill-scan:{candidate.seed_id}",
            extra={
                "detected_via": "ann-cluster",
                "member_count": len(candidate.member_ids),
                "time_spread_days": round(candidate.time_spread_days, 2),
                "avg_score": round(candidate.avg_score, 3),
            },
        )
    except ss.SuggestionAlreadyExists as e:
        return LabeledCandidate(
            candidate_seed_id=candidate.seed_id,
            status="skipped-existing",
            slug=str(slug),
            reason=str(e),
        )
    except (ValueError, ss.SkillSuggestionError) as e:
        return LabeledCandidate(
            candidate_seed_id=candidate.seed_id,
            status="error",
            slug=str(slug),
            reason=str(e),
        )

    return LabeledCandidate(
        candidate_seed_id=candidate.seed_id,
        status="created",
        slug=sug.slug,
        draft_path=str(sug.path),
    )


async def label_candidates(
    candidates: list[SkillCandidate],
    *,
    timeout: float = 90.0,
    run_fn: RunSkillFn | None = None,
) -> list[LabeledCandidate]:
    """Label every candidate in turn, swallowing per-candidate failures.

    Sequential (not concurrent) because Hermes serializes its own
    requests anyway and parallel calls just add tail-latency variance.
    """
    out: list[LabeledCandidate] = []
    for c in candidates:
        out.append(await label_candidate(c, timeout=timeout, run_fn=run_fn))
    return out


__all__ = [
    "LabeledCandidate",
    "format_candidate_opener",
    "label_candidate",
    "label_candidates",
    "parse_label_response",
]
