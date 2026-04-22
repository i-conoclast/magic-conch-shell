"""Tests for structured-capture templates (FR-A2)."""
from __future__ import annotations

from pathlib import Path

import frontmatter
import pytest

from mcs.adapters.memory import capture_structured
from mcs.adapters.templates import (
    TemplateError,
    assemble_body,
    coerce_field_value,
    list_templates,
    load_template,
)


# ─── load_template / list_templates ────────────────────────────────────

def test_list_returns_bundled_templates() -> None:
    names = list_templates()
    # Three default templates live at templates/ in the repo root.
    assert "interview-note" in names
    assert "meeting-note" in names
    assert "experiment-log" in names


def test_load_interview_template_fields() -> None:
    t = load_template("interview-note")
    assert t.name == "interview-note"
    assert t.domain == "career"
    assert t.default_type == "note"
    kinds = {f.name: f.kind for f in t.fields}
    assert kinds["company"] == "entity-ref"
    assert kinds["interviewers"] == "entity-ref-list"
    assert kinds["round"] == "enum"
    assert "Key topics" in t.body_sections


def test_load_missing_template_errors() -> None:
    with pytest.raises(TemplateError):
        load_template("no-such-template")


def test_load_rejects_unknown_field_kind(tmp_path: Path, monkeypatch) -> None:
    """Malformed field kind in a sandbox template surfaces as TemplateError."""
    tpl_dir = tmp_path / "templates"
    tpl_dir.mkdir()
    (tpl_dir / "bad.md").write_text(
        "---\n"
        "template: bad\n"
        "domain: general\n"
        "fields:\n"
        "  - name: x\n"
        "    kind: hologram\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )
    from mcs.adapters import templates as t_mod
    monkeypatch.setattr(t_mod, "_templates_dir", lambda: tpl_dir)
    with pytest.raises(TemplateError, match="invalid kind"):
        load_template("bad")


# ─── coerce_field_value ────────────────────────────────────────────────

def test_coerce_text_trims() -> None:
    t = load_template("meeting-note")
    ctx_field = next(f for f in t.fields if f.name == "context")
    assert coerce_field_value(ctx_field, "   hello  ") == "hello"


def test_coerce_enum_validates() -> None:
    t = load_template("experiment-log")
    status = next(f for f in t.fields if f.name == "status")
    assert coerce_field_value(status, "running") == "running"
    with pytest.raises(TemplateError):
        coerce_field_value(status, "hallucinating")


def test_coerce_entity_ref_list_splits_csv() -> None:
    t = load_template("interview-note")
    interviewers = next(f for f in t.fields if f.name == "interviewers")
    out = coerce_field_value(interviewers, "people/jane, people/bob ,  people/alice")
    assert out == ["people/jane", "people/bob", "people/alice"]


def test_coerce_empty_optional_returns_none() -> None:
    t = load_template("interview-note")
    company = next(f for f in t.fields if f.name == "company")
    assert coerce_field_value(company, "") is None


def test_coerce_empty_list_returns_empty_list() -> None:
    t = load_template("interview-note")
    interviewers = next(f for f in t.fields if f.name == "interviewers")
    assert coerce_field_value(interviewers, "") == []


# ─── assemble_body ─────────────────────────────────────────────────────

def test_assemble_body_renders_sections() -> None:
    t = load_template("interview-note")
    body = assemble_body(t)
    for sec in t.body_sections:
        assert f"## {sec}" in body


# ─── capture_structured (writes a file) ────────────────────────────────

def test_capture_structured_writes_and_populates_entities(tmp_brain: Path) -> None:
    result = capture_structured(
        template="interview-note",
        fields={
            "company": "companies/anthropic",
            "interviewers": "people/jane-smith, people/bob-kim",
            "round": "1차",
            "format": "온라인",
        },
        title="anthropic-mle-1st",
    )
    assert result.path.exists()
    assert result.path.is_relative_to(tmp_brain / "domains" / "career")

    meta = frontmatter.load(result.path).metadata
    assert meta["template"] == "interview-note"
    assert meta["company"] == "companies/anthropic"
    assert meta["interviewers"] == ["people/jane-smith", "people/bob-kim"]
    assert meta["round"] == "1차"
    assert set(meta["entities"]) == {
        "companies/anthropic",
        "people/jane-smith",
        "people/bob-kim",
    }


def test_capture_structured_skips_empty_fields(tmp_brain: Path) -> None:
    result = capture_structured(
        template="meeting-note",
        fields={"attendees": "", "context": "quick sync"},
        title="sync",
    )
    meta = frontmatter.load(result.path).metadata
    # attendees was empty → not written as a key (entities stays empty list too)
    assert "attendees" not in meta or meta.get("attendees") in (None, [])
    assert meta["context"] == "quick sync"


def test_capture_structured_unknown_template_raises(tmp_brain: Path) -> None:
    with pytest.raises(TemplateError):
        capture_structured(template="no-such-template", fields={})


def test_capture_structured_body_has_scaffold(tmp_brain: Path) -> None:
    result = capture_structured(
        template="experiment-log",
        fields={"project": "LoRA ablation", "status": "running"},
        title="lora-ablation",
    )
    body = frontmatter.load(result.path).content
    assert "## Setup" in body
    assert "## Observations" in body
    assert "## Next step" in body
