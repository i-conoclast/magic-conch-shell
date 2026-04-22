---
template: experiment-log
domain: ml
default_type: note
fields:
  - name: project
    kind: text
    prompt: "Project name (short)"
    required: false
  - name: hypothesis
    kind: text
    prompt: "Hypothesis under test"
    required: false
  - name: status
    kind: enum
    values: ["running", "blocked", "done", "abandoned"]
    prompt: "Status"
    required: false
body_sections:
  - Setup
  - Observations
  - Metrics
  - Next step
---

# Experiment log

Lightweight template for ML/learning experiments. Focused on what
changed and what to try next, not a full lab notebook.
