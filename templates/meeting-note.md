---
template: meeting-note
domain: general
default_type: note
fields:
  - name: attendees
    kind: entity-ref-list
    entity_kind: people
    prompt: "Attendees (comma-separated people/<slug>)"
    required: false
  - name: context
    kind: text
    prompt: "One-line context"
    required: false
body_sections:
  - Agenda
  - Decisions
  - Action items
  - Open questions
---

# Meeting note

Minutes template. Keep decisions and action items separate so back-links
to people entities stay useful.
