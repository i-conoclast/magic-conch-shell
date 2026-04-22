"""Template loader for FR-A2 structured capture.

Templates live at `<repo_root>/templates/<name>.md` with YAML frontmatter
describing fields. Field schema:

  - name:         str             field key, becomes a frontmatter key
  - kind:         one of:
                    "text"             free text
                    "enum"             one of `values`
                    "entity-ref"       single entity slug
                    "entity-ref-list"  comma-separated slugs → list
  - prompt:       str             shown to the CLI user
  - values:       list[str]       required for kind=enum
  - entity_kind:  str             optional, for entity-ref(-list)
  - required:     bool            default False (empty allowed)

Top-level keys:
  - template       str            name, usually file stem
  - domain         str            default brain domain to route into
  - default_type   str            usually "note"
  - body_sections  list[str]      rendered as ## headers in the body scaffold
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter

from mcs.adapters.memory import DOMAINS
from mcs.config import load_settings


class TemplateError(ValueError):
    """Raised for missing / malformed templates or field values."""


_ALLOWED_KINDS = frozenset({"text", "enum", "entity-ref", "entity-ref-list"})


@dataclass
class TemplateField:
    name: str
    kind: str
    prompt: str
    required: bool = False
    values: list[str] = field(default_factory=list)
    entity_kind: str | None = None


@dataclass
class Template:
    name: str
    domain: str
    default_type: str
    fields: list[TemplateField]
    body_sections: list[str]
    description: str = ""


def _templates_dir() -> Path:
    return load_settings().repo_root.resolve() / "templates"


def list_templates() -> list[str]:
    """Return available template names (file stems)."""
    root = _templates_dir()
    if not root.exists():
        return []
    return sorted(p.stem for p in root.glob("*.md") if not p.name.startswith("."))


def load_template(name: str) -> Template:
    """Parse templates/<name>.md. Raises TemplateError on any issue."""
    root = _templates_dir()
    path = root / f"{name}.md"
    if not path.exists():
        raise TemplateError(
            f"template {name!r} not found. Available: {list_templates() or '(none)'}"
        )

    try:
        post = frontmatter.load(path)
    except Exception as e:
        raise TemplateError(f"failed to parse {path}: {e}") from e

    meta = post.metadata or {}
    domain = meta.get("domain")
    if domain and domain not in DOMAINS:
        raise TemplateError(
            f"template {name!r} specifies unknown domain {domain!r}"
        )

    raw_fields = meta.get("fields") or []
    fields: list[TemplateField] = []
    for i, f in enumerate(raw_fields):
        if not isinstance(f, dict):
            raise TemplateError(f"{name}: field[{i}] is not a mapping")
        kind = f.get("kind")
        if kind not in _ALLOWED_KINDS:
            raise TemplateError(
                f"{name}: field[{i}] has invalid kind {kind!r} "
                f"(must be one of {sorted(_ALLOWED_KINDS)})"
            )
        if kind == "enum" and not f.get("values"):
            raise TemplateError(f"{name}: enum field {f.get('name')!r} needs `values`")
        fields.append(
            TemplateField(
                name=str(f["name"]),
                kind=str(kind),
                prompt=str(f.get("prompt") or f["name"]),
                required=bool(f.get("required") or False),
                values=list(f.get("values") or []),
                entity_kind=f.get("entity_kind"),
            )
        )

    return Template(
        name=str(meta.get("template") or name),
        domain=str(domain or "general"),
        default_type=str(meta.get("default_type") or "note"),
        fields=fields,
        body_sections=list(meta.get("body_sections") or []),
        description=(post.content or "").strip(),
    )


# ─── field coercion ─────────────────────────────────────────────────────

def coerce_field_value(field: TemplateField, raw: str) -> Any:
    """Turn a raw CLI/MCP string into the appropriate shape for this field.

    Empty strings map to None (or [] for list kinds). Enum values are
    validated; entity-ref-list splits on commas and strips whitespace.
    """
    s = (raw or "").strip()

    if field.kind == "entity-ref-list":
        if not s:
            return []
        return [tok.strip() for tok in s.split(",") if tok.strip()]

    if not s:
        if field.required:
            raise TemplateError(f"field {field.name!r} is required")
        return None

    if field.kind == "enum":
        if s not in field.values:
            raise TemplateError(
                f"field {field.name!r}: {s!r} not in {field.values}"
            )
        return s

    # text and entity-ref: pass through trimmed string
    return s


def assemble_body(template: Template) -> str:
    """Return a markdown body scaffold with one ## section per body_sections entry."""
    if not template.body_sections:
        return ""
    return "\n\n".join(f"## {s}\n" for s in template.body_sections) + "\n"
