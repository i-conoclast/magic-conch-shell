---
template: interview-note
domain: career
default_type: note
fields:
  - name: company
    kind: entity-ref
    entity_kind: companies
    prompt: "Company slug (companies/anthropic)"
    required: false
  - name: interviewers
    kind: entity-ref-list
    entity_kind: people
    prompt: "Interviewers (comma-separated people/jane-smith, people/bob-kim)"
    required: false
  - name: round
    kind: enum
    values: ["1차", "2차", "3차", "final"]
    prompt: "Round"
    required: false
  - name: format
    kind: enum
    values: ["온라인", "오프라인", "전화"]
    prompt: "Format"
    required: false
body_sections:
  - Key topics
  - Impression
  - Next steps
  - Follow-up actions
---

# Interview note

Template for post-interview debriefs.
Edits after save belong in `brain/domains/career/...`.
