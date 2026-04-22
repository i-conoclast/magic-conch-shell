# Project: magic-conch-shell

A personal life + career memory and agent platform.
Read `SOUL.md` for personality. Read this file for project conventions.

## Skills (skills/)

| Skill | Trigger | Purpose |
|---|---|---|
| morning-brief | cron 07:00 KST or /brief | Generate morning briefing |
| evening-retro | cron 22:00 KST or /retro | Run evening review + approval inbox |
| weekly-review | cron Sun 20:00 KST | Weekly summary and outlook |
| conch-answer | any incoming query | Route tone: consulting / oracle / hybrid |
| entity-extract | after record save | Detect new entities, create drafts |
| plan-confirm | after morning-brief reply | Converge on today's plan via chat |

## Agents (agents/)

| Agent | Persona |
|---|---|
| planner | Serious consulting persona |
| oracle | Light one-line conch responder |
| tutor-english | English conversation session runner |
| tutor-ml | ML study session runner |
| interviewer | Mock-interview runner |
| advisor-finance | Finance advisory runner |

## Commands (commands/)

`/brief`, `/retro`, `/weekly`, `/english`, `/ml`, `/mock-interview`, `/finance`

## Project Structure

- `skills/` — knowledge (SKILL.md, auto-triggered)
- `agents/` — subagent personas
- `commands/` — explicit entry points
- `tools/` — Python tools (one per external system)
- `hooks/` — `command` + `agent` types only (MVP)
- `mcp/` — MCP server exposing mcs to Hermes
- `brain/` — user data (source of truth)
  - `daily/`, `domains/`, `entities/`, `signals/`, `plans/`
  - `USER.md` — user profile (learned + manual); symlinked at project root
  - `MEMORY.md` — memory index for Hermes
  - `session-state/` — per-agent progress and logs
- `.brain/` — cache (memsearch DB, queues, state)

## Conventions

- **Domains (7)**: `career`, `health-physical`, `health-mental`, `relationships`, `finance`, `ml`, `general`
- **Entity kinds (4)**: `people`, `companies`, `jobs`, `books`
- **Slug**:
  - Typed notes: `YYYY-MM-DD-{kebab-title}` (max 50 chars)
  - Auto-generated: `YYYY-MM-DD-HHmmss`
- **Timezone**: KST (+09:00), no UTC.
- **Language**: Korean and English mix is allowed and expected.
- **File format**: Markdown + YAML frontmatter.

## Boundaries

### Always do
- Force local LLM for sensitive domains (finance, relationships, mental, health).
- Route external writes through the local queue (Notion, iMessage).
- Batch approvals into the evening retro.
- Persist user input immediately — no silent drops.

### Ask first
- Promote an entity draft to the formal entities folder.
- Auto-promote a repeated interaction into a new skill.
- Update learned items in `USER.md`.
- Push a confirmed plan to the external task system.

### Never do
- Send nagging or absence-detection notifications.
- Give the same oracle answer three times consecutively.
- Overwrite the manual section of `USER.md`.
- Transmit sensitive data to external LLMs.
- Finalize a plan without explicit user confirmation.
- Auto-modify `SOUL.md` or this `AGENTS.md`.

## Tools

Each skill and agent declares what it may use in the frontmatter `tools:` field.

| Tool | Scope |
|---|---|
| `notion` | Notion DB and calendar read/write |
| `memory` | brain/ search, capture, entity ops |
| `llm` | Codex OAuth (primary) and Ollama (local) routing |
| `hermes` | Hermes bridge — subagent spawn, messaging |
| `file` | brain/ file operations |

## Integration

- mcs is exposed as an **MCP server** (`mcp/mcs-server.py`, stdio transport).
- Hermes accesses mcs through its MCP client.
- External task system and calendar: **Notion**.
- LLMs: **Codex OAuth** (primary) + **Ollama local** (fallback and sensitive).
- Chat: Hermes built-in iMessage (AppleScript).

## Scheduler

Hermes built-in cron handles all scheduled runs (no launchd).
Active schedules:
- `0 7 * * *` → `/brief`
- `0 22 * * *` → `/retro`
- `0 20 * * 0` → `/weekly`
