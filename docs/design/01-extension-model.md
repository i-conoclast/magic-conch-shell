# 01. Extension Model

**작성일**: 2026-04-19
**전제**: [00-architecture.md](00-architecture.md), [02-data-model.md](02-data-model.md)

magic-conch-shell은 **플랫폼**. 어떤 skill·agent·command·tool·hook·integration이든 **표준 포맷으로 추가 가능**. 이 문서는 **각 확장 포인트의 규격**을 정의한다.

---

## 1. 확장 포인트 6종

| 확장 포인트 | 파일 위치 | 포맷 | 자동 로딩 |
|---|---|---|---|
| **Skill** | `skills/{name}/SKILL.md` | Markdown + YAML frontmatter | ✅ 재시작 불필요 |
| **Agent** | `agents/{name}.md` | Markdown + YAML frontmatter | ✅ |
| **Command** | `commands/{name}.md` | Markdown + YAML frontmatter | ✅ |
| **Tool** | `tools/{name}.py` | Python 모듈 | 재시작 필요 |
| **Hook** | `hooks/{type}/{name}.{sh,md}` | Shell / Markdown | ✅ |
| **MCP Integration** | `mcp/{name}-server.py` 또는 외부 | Python (in-process) | 재시작 필요 |

---

## 2. Skill 규격

### 2.1 파일 구조
```
skills/{skill-name}/
├── SKILL.md          ← 필수. 진입점
├── template.md       ← 선택. 참조 파일
├── examples/         ← 선택. 예시
└── scripts/          ← 선택. 실행 스크립트
```

### 2.2 SKILL.md 프론트매터

```yaml
---
name: string                    # 필수, kebab-case, 고유
description: string             # 필수, 150자 이내, trigger 매칭용
trigger:                        # 필수, 배열
  - cron: string                # crontab 형식
  - command: string             # /명령
  - event: string               # on_capture, on_retro 등
tools: [string]                 # 필수, 빈 배열 허용
model: string                   # 선택: codex-oauth | ollama-local | auto (기본)
sensitive: boolean              # 선택: true면 로컬 LLM 강제
max_turns: int                  # 선택: 대화 턴 상한
timeout: int                    # 선택: 실행 시간 상한 (초)
---
```

### 2.3 본문 권장 섹션

```markdown
# {Skill Name}

## When to use
(trigger 외에 언제 이걸 쓰는지 자연어)

## Steps
1. (단계별 지침)

## Output format
(결과물 포맷 — 템플릿 참조 가능)

## References
- [template.md](template.md)
- [examples/](examples/)
```

### 2.4 예시

```markdown
---
name: morning-brief
description: Generate daily morning briefing with today's tasks, yesterday misses, and external signals
trigger:
  - cron: "0 7 * * *"
  - command: /brief
tools: [memory, notion, llm, file]
model: codex-oauth
timeout: 60
---

# Morning Brief

## Steps
1. memory.search에서 어제 미완료·최근 변화 추출
2. notion.read_db에서 오늘 태스크·캘린더 읽기
3. llm.call(codex-oauth)로 브리핑 생성
4. file.write로 brain/daily/ 저장
5. hermes.send_imessage로 전송
```

### 2.5 Progressive Disclosure

- 기본 컨텍스트: **모든 SKILL.md의 frontmatter만**
- Trigger 매치 시: 해당 SKILL.md **본문 로드**
- 본문이 참조 파일 언급: **on-demand bash read**

---

## 3. Agent 규격

### 3.1 파일 구조
```
agents/{agent-name}.md
```
단일 파일. Skill과 달리 참조 파일 없음 (자체 완결).

### 3.2 프론트매터

```yaml
---
name: string                    # 필수, kebab-case
description: string             # 필수
tools: [string]                 # 필수
model: string                   # 선택
sensitive: boolean              # 선택
isolation: string               # 필수: "fork" | "shared"
state_path: string              # 선택: brain/session-state/{name}/
max_turns: int                  # 선택
memory: string                  # 선택: "persistent" | "session" | "none"
background: boolean             # 선택: true면 백그라운드 실행 허용
---
```

**`isolation` 값**:
- `fork`: 자체 컨텍스트 스레드, 메인 대화와 격리
- `shared`: 메인 대화 컨텍스트 유지

### 3.3 본문 권장 섹션

```markdown
# {Agent Name}

## Persona
(이 에이전트의 성격·말투·역할)

## Session structure
1. (세션 시작 방식)
2. (진행 방식)
3. (종료·저장 방식)

## Rules
- (에이전트가 지켜야 할 규칙)
```

### 3.4 예시

```markdown
---
name: tutor-english
description: English conversation session runner. Resumes from last session progress.
tools: [memory, llm, hermes]
model: ollama-local
isolation: fork
state_path: brain/session-state/tutor-english/
max_turns: 50
memory: persistent
---

# English Tutor

## Persona
You are an English conversation partner. Adapt to user's level.
Use natural, native-like English. Patient and encouraging.

## Session structure
1. Read state.yaml from state_path — last topic, level, upcoming
2. Greet and recap last session briefly
3. Conversation flow based on user's current level
4. Correct grammar gently, explain when needed
5. Save progress and today's log to state_path/logs/

## Rules
- No Korean translation unless explicitly asked
- Adjust difficulty based on response quality
- Keep sessions under 30 minutes unless user wants more
```

---

## 4. Command 규격

### 4.1 파일 구조
```
commands/{command-name}.md
```

### 4.2 프론트매터

```yaml
---
name: string                    # 필수, 슬래시 명령 이름 (/xxx)
description: string             # 필수
agent: string                   # 선택: 이 커맨드가 호출하는 agent 이름
skill: string                   # 선택: agent 대신 skill 직접 호출 가능
aliases: [string]               # 선택: 별칭 목록
args: [ArgSpec]                 # 선택: 인자 스펙 (Typer 형식)
---
```

**`agent` vs `skill`**: 둘 중 하나만 지정. `agent`는 전용 퍼소나로 fork, `skill`은 현재 컨텍스트에서 즉시 실행.

### 4.3 예시

```markdown
---
name: english
description: Start English conversation session
agent: tutor-english
aliases: [eng, 영어]
args:
  - name: new
    type: flag
    help: Reset session state
---

# /english

Invokes the English conversation tutor agent.

- Default: resume from last session
- `/english --new`: reset state and start fresh
```

### 4.4 Typer CLI 대응

mcs는 `commands/` 폴더를 스캔해 Typer 서브커맨드 자동 등록.
- Hermes slash: `/english`
- mcs CLI: `mcs english`
- 두 경로가 동일 동작

---

## 5. Tool 규격

### 5.1 파일 구조
```
tools/{tool-name}.py
```
Python 모듈. 외부 시스템 또는 주 도메인당 1개.

### 5.2 인터페이스

```python
"""
notion.py — Notion DB and calendar integration
"""
from typing import Optional

async def read_db(db_id: str, filter: Optional[dict] = None) -> list[dict]:
    """Read from a Notion database."""
    ...

async def create_page(db_id: str, properties: dict) -> str:
    """Create a page. Returns page_id."""
    ...

async def update_page(page_id: str, properties: dict) -> None:
    """Update an existing page."""
    ...

# ... 기타 함수

# 메타데이터 (선택, MCP 노출용)
TOOL_METADATA = {
    "name": "notion",
    "description": "Notion DB and calendar read/write",
    "operations": ["read_db", "create_page", "update_page", "list_calendars", "read_calendar"]
}
```

### 5.3 MCP 노출

`mcp/mcs-server.py`가 `tools/` 모듈을 import하여 MCP tool로 등록:

```python
# mcp/mcs-server.py
from mcp import Server
from tools import notion, memory, llm, hermes, file

server = Server("mcs")

# 각 tool의 함수를 MCP tool로 등록
@server.tool("notion.read_db", "Read from a Notion database")
async def notion_read_db(db_id: str, filter: dict = None):
    return await notion.read_db(db_id, filter)

# ... 나머지 함수들도 동일 패턴
```

### 5.4 Tool scope 원칙

**외부 시스템 또는 주 도메인당 1개**:
- ✅ `notion` (모든 Notion 연산)
- ✅ `memory` (모든 brain/ 연산)
- ✅ `llm` (모든 LLM 호출)
- ❌ `notion_read` + `notion_write` 세분화 금지
- ❌ `memory_search` + `memory_capture` 세분화 금지

스킬이 `tools: [notion]` 선언하면 notion의 모든 연산 허용.

---

## 6. Hook 규격 (MVP 2종)

### 6.1 command hook

```
hooks/command/{name}.sh
```

**실행 환경**:
- stdin: JSON 이벤트 데이터
- stdout: 로그
- exit 0: 진행
- exit 2: 차단 (stderr에 이유)

**이벤트 타입**:
- `pre-tool-use`: 도구 호출 직전
- `post-tool-use`: 도구 호출 직후
- `pre-external-write`: 외부 쓰기 직전
- `pre-push`: Notion push 직전

**예시**:
```bash
#!/bin/bash
# hooks/command/pre-external-write.sh

input=$(cat)
sensitive=$(echo "$input" | jq -r '.sensitive')
tool=$(echo "$input" | jq -r '.tool')

if [[ "$sensitive" == "true" && "$tool" == "llm.call" ]]; then
  model=$(echo "$input" | jq -r '.args.model')
  if [[ "$model" == "codex-oauth" ]]; then
    echo "blocked: sensitive data to external LLM" >&2
    exit 2
  fi
fi

exit 0
```

### 6.2 agent hook

```
hooks/agent/{name}.md
```

프론트매터 + 본문 (agent와 동일 포맷).

**차이점**: 트리거가 사용자 호출이 아니라 **시스템 이벤트**.

**예시**:
```markdown
---
name: verify-plan
description: Validate plan coherence before Notion push
trigger:
  - event: pre-push
tools: [memory]
isolation: fork
max_turns: 5
---

# Verify Plan

Given a confirmed plan in input, check:
1. Conflicts with today's calendar?
2. Aligns with stated KR priorities?
3. Logical inconsistency?

Return: `{ status: "ok" | "warn" | "block", reason?: string }`
```

### 6.3 Hook 등록

`~/.hermes/config.yaml` 또는 `config.yaml`:
```yaml
hooks:
  pre-external-write: hooks/command/pre-external-write.sh
  pre-push: hooks/agent/verify-plan.md
```

### 6.4 Hook 권한

모든 hook은 `tools:` 필드 필수. hook도 엄격한 최소 권한.

---

## 7. MCP Server 규격

### 7.1 서버 구조 (FastMCP 2.x 기반)

**선택 라이브러리**: [`fastmcp`](https://github.com/jlowin/fastmcp) 2.x
- 2026 사실상 표준 MCP 프레임워크
- 데코레이터 API, 타입 힌트로 입력 스키마 자동 생성
- 공식 SDK(`mcp`) 위에 구축됨

```python
# mcp/mcs-server.py
from fastmcp import FastMCP
from tools import notion, memory, llm, hermes, file

mcp = FastMCP(
    name="mcs",
    version="0.1.0",
    instructions="magic-conch-shell personal life brain + agent platform"
)

# ─── Memory tools ───────────────────────────────────────────
@mcp.tool()
async def memory_search(
    query: str,
    domain: str | None = None,
    entity: str | None = None,
    top_k: int = 10,
) -> list[dict]:
    """Search brain/ with hybrid vector + BM25 retrieval."""
    return await memory.search(query, domain=domain, entity=entity, top_k=top_k)

@mcp.tool()
async def memory_capture(
    text: str,
    domain: str | None = None,
    entities: list[str] | None = None,
    source: str = "hermes",
) -> dict:
    """Capture free-form text into brain/ with optional metadata."""
    return await memory.capture(text=text, domain=domain, entities=entities, source=source)

@mcp.tool()
async def memory_entities_list(kind: str, min_backlinks: int = 0) -> list[dict]:
    """List entities of a kind (people | companies | jobs | books)."""
    return await memory.entities_list(kind=kind, min_backlinks=min_backlinks)

# ─── Notion tools ───────────────────────────────────────────
@mcp.tool()
async def notion_read_db(db_id: str, filter: dict | None = None) -> list[dict]:
    """Read pages from a Notion database."""
    return await notion.read_db(db_id, filter)

@mcp.tool()
async def notion_create_page(db_id: str, properties: dict) -> str:
    """Create a page in a Notion database. Returns page_id."""
    return await notion.create_page(db_id, properties)

# ─── LLM tool ───────────────────────────────────────────────
@mcp.tool()
async def llm_call(
    prompt: str,
    model: str | None = None,
    sensitive: bool = False,
    max_tokens: int = 1024,
) -> str:
    """Call LLM through the central router (Codex OAuth or Ollama)."""
    return await llm.call(prompt=prompt, model=model, sensitive=sensitive, max_tokens=max_tokens)

# ─── File tools ─────────────────────────────────────────────
@mcp.tool()
async def file_read(path: str) -> str:
    """Read a brain/ file."""
    return await file.read(path)

@mcp.tool()
async def file_write(path: str, content: str) -> None:
    """Write a brain/ file."""
    await file.write(path, content)

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

**특징**:
- `@mcp.tool()` 데코레이터 하나로 등록
- 타입 힌트(`str | None`, `list[dict]`, 기본값)로 JSON Schema 자동 생성
- Pydantic 2 내장 — 입력 검증
- docstring이 tool description으로 사용됨

### 7.2 전송 방식

MVP: **stdio** (Hermes ↔ mcs 같은 기기 전제)
v1.0+: HTTP 옵션 (다른 기기 연동 필요시)

### 7.3 인증

MVP: 없음 (로컬 전용, 같은 사용자)
v1.0+: 필요 시 토큰 기반

### 7.4 Hermes 연동

```yaml
# ~/.hermes/config.yaml
mcp_servers:
  mcs:
    transport: stdio
    command: python
    args: [~/magic-conch-shell/mcp/mcs-server.py]
    env:
      MCS_CONFIG: ~/magic-conch-shell/config.yaml
```

---

## 8. 확장 예시 시나리오

### 8.1 새 학습 주제 추가 (Go 공부)

파일 2개만 작성:

1. `agents/tutor-go.md`:
```markdown
---
name: tutor-go
description: Go language study session runner
tools: [memory, llm]
model: ollama-local
isolation: fork
state_path: brain/session-state/tutor-go/
---

# Go Tutor
(persona)
```

2. `commands/go.md`:
```markdown
---
name: go
description: Start Go study session
agent: tutor-go
---
```

→ 즉시 사용 가능. `/go` 또는 `mcs go` 호출.

### 8.2 새 외부 시스템 연동 (Slack)

파일 2개:

1. `tools/slack.py` (Python 모듈):
```python
async def send_message(channel: str, text: str): ...
async def read_messages(channel: str, limit: int = 10): ...
```

2. `mcp/mcs-server.py`에 tool 등록 추가.

3. 사용할 skill·agent에 `tools: [slack]` 추가.

→ 재시작 필요 (tools 모듈은 코드이므로).

### 8.3 새 도메인 추가 (취미)

1. `brain/domains/hobby/` 디렉토리 생성
2. `AGENTS.md`의 "Conventions > Domains" 항목에 `hobby` 추가
3. 끝. 캡처 시 `--domain hobby` 지정 가능.

### 8.4 새 엔티티 타입 추가 (장소)

1. `brain/entities/places/` 생성
2. `AGENTS.md`의 "Entity kinds" 갱신
3. `tools/memory.py`에 places 템플릿 추가 (선택)
4. `skills/entity-extract/SKILL.md`에 places 감지 로직 추가

---

## 9. 확장 규약 요약

| 확장 | 필요 파일 | 재시작 | 권장 범위 |
|---|---|---|---|
| Skill | `SKILL.md` | ❌ | 재사용 가능한 지식 |
| Agent | `{name}.md` | ❌ | 전용 퍼소나 (세션 기반) |
| Command | `{name}.md` | ❌ | CLI/slash 진입점 |
| Tool | `tools/{name}.py` + MCP 등록 | ✅ | 외부 시스템당 1개 |
| Hook | `hooks/{type}/{name}.*` | ❌ | lifecycle 이벤트 |
| MCP Integration | `mcp/*.py` | ✅ | 외부 도구 재노출 |

---

## 10. 버저닝·호환성

- SKILL.md·Agent·Command 파일 프론트매터 **하위 호환 유지**
- 새 필드 추가는 optional
- 기존 필드 의미 변경 시 major version bump
- Anthropic Skills / Claude Code skills와 호환성 **노력** (표준 변경 시 따라감)

---

## 11. 공유·배포 (v1.0+)

개인 확장을 다른 사용자가 쓰도록 배포하려면 **plugin 포맷** 사용:

```
my-plugin/
├── .mcs-plugin/
│   └── plugin.json              (메타데이터)
├── skills/
├── agents/
├── commands/
├── tools/
├── hooks/
└── README.md
```

plugin.json:
```json
{
  "name": "my-plugin",
  "version": "0.1.0",
  "description": "...",
  "mcs_version": ">=0.1.0",
  "author": "..."
}
```

설치:
```bash
mcs plugin install my-plugin
```

→ plugin 내용을 mcs의 적절한 디렉토리로 복사.

**MVP는 plugin 지원 없음** — 구조만 미리 고려.

---

## 12. 원칙 요약

1. **모든 확장은 마크다운 + YAML 프론트매터** 표준
2. **Skills·Agents·Commands는 재시작 불필요** (파일 drop-in)
3. **Tools·MCP는 코드라 재시작 필요**
4. **최소 권한**: 각 확장이 `tools:` 명시
5. **외부 시스템당 tool 1개**: 세분화 금지
6. **Hook MVP 2종**: command + agent
7. **MCP stdio**: 로컬 전용
8. **공유 가능한 plugin 포맷 미래 고려** (MVP 범위 밖)
