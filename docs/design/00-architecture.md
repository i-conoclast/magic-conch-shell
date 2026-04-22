# 00. Architecture

**작성일**: 2026-04-19
**최종 갱신**: 2026-04-19 (Claude Code 3-tier + identity layer + MCP 반영)
**전제**: [tech-comparison/00-decisions.md](tech-comparison/00-decisions.md)

---

## 1. 레이어 개요 (6 계층)

magic-conch-shell의 전체 구조는 **6개 레이어**로 이해할 수 있다.

| 레이어 | 역할 | 주요 파일·컴포넌트 |
|---|---|---|
| **1. Identity** | 에이전트가 누구인가 | `SOUL.md`, `AGENTS.md`, `brain/USER.md` (+ symlink) |
| **2. Knowledge** | 에이전트가 무엇을 아는가 | `skills/`, `brain/MEMORY.md`, `brain/*` |
| **3. Execution** | 에이전트가 어떻게 행동하는가 | `agents/`, `commands/`, `tools/`, `hooks/` |
| **4. Platform** | 어디서 돌아가는가 | Hermes runtime + Ollama + iMessage adapter |
| **5. Data** | 무엇이 지속되는가 | `brain/` (SSoT) + `.brain/` (캐시) |
| **6. Integration** | 외부 세계와 어떻게 연결되는가 | `mcp/` (MCP 서버) + Notion + Codex OAuth |

---

## 2. 전체 구성도

```
┌────────────────────────────────────────────────────────────────────────┐
│  Mac mini M4 Pro 64GB (허브, 24/7)                                     │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  Ollama 0.21 (*:11434) — MLX runner (OLLAMA_USE_MLX=1)           │ │
│  │  ├─ Qwen3.6:35b-a3b-mxfp8 (MoE 35B, 3B active, 검증됨)           │ │
│  │  └─ BGE-M3 (embedding, memsearch용)                              │ │
│  │  관리: llm-server-template-ollama repo (config + launchd)         │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                              ▲                                         │
│                              │ HTTP (OpenAI-compat)                    │
│  ┌───────────────────────────┴──────────────────────────────────────┐ │
│  │  Hermes Agent (~/.hermes/)                                        │ │
│  │                                                                   │ │
│  │  System prompt auto-assembled from:                               │ │
│  │    1. SOUL.md          ← 인격 (3 Beliefs, style, avoid)           │ │
│  │    2. AGENTS.md        ← 프로젝트 관례 (skills·boundaries·tools) │ │
│  │    3. USER.md          ← 사용자 프로필 (symlink→brain/USER.md)    │ │
│  │    4. Relevant skills  ← on-demand (progressive disclosure)       │ │
│  │    5. Active agent     ← subagent persona (있을 때)               │ │
│  │                                                                   │ │
│  │  ├─ skills/  ← config.yaml로 등록 (magic-conch-shell/skills/)     │ │
│  │  ├─ agents/  ← subagent personas                                  │ │
│  │  ├─ Hermes 내장 cron  ← /brief·/retro·/weekly 스케줄              │ │
│  │  ├─ iMessage adapter (AppleScript)                                │ │
│  │  └─ MCP client         ← mcs MCP 서버 호출                        │ │
│  └───────────────────────────┬──────────────────────────────────────┘ │
│                              │ MCP (stdio)                             │
│  ┌───────────────────────────▼──────────────────────────────────────┐ │
│  │  magic-conch-shell (Python 3.11 + uv)                             │ │
│  │                                                                   │ │
│  │  ┌────────────────────────────────────────────────────────────┐  │ │
│  │  │  mcp/mcs-server.py                                         │  │ │
│  │  │  ├─ tool: memory.search, memory.capture, memory.entities   │  │ │
│  │  │  ├─ tool: notion.read, notion.write                        │  │ │
│  │  │  ├─ tool: llm.call (로컬↔외부 라우팅)                      │  │ │
│  │  │  └─ tool: file.* (brain/ 조작)                             │  │ │
│  │  └────────────────────────────────────────────────────────────┘  │ │
│  │                                                                   │ │
│  │  CLI entry: mcs (Typer + Rich) — 직접 호출도 가능                  │ │
│  │                                                                   │ │
│  │  ┌────────────────────────────────────────────────────────────┐  │ │
│  │  │  src/mcs/                                                  │  │ │
│  │  │  ├─ engine/        ← 요청 라우팅 (MCP·CLI·Hermes)          │  │ │
│  │  │  ├─ tools/         ← notion·memory·llm·hermes·file (5종)   │  │ │
│  │  │  ├─ hooks/         ← command·agent 타입 (MVP 2종만)        │  │ │
│  │  │  ├─ commands/      ← Typer CLI commands                    │  │ │
│  │  │  └─ adapters/      ← memsearch·notion-client·codex         │  │ │
│  │  └────────────────────────────────────────────────────────────┘  │ │
│  │                                                                   │ │
│  │  ┌────────────────────────────────────────────────────────────┐  │ │
│  │  │  memsearch + Milvus Lite (embedded)                        │  │ │
│  │  │  └─ .brain/memsearch-db/                                   │  │ │
│  │  └────────────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────┬──────────────────────────────────────┘ │
│                              │                                         │
│           ┌──────────────────┼──────────────────┐                      │
│           ▼                  ▼                  ▼                      │
│  ┌────────────────┐  ┌───────────────┐  ┌──────────────┐               │
│  │ brain/ (SSoT)  │  │ .brain/ cache │  │ skills/      │               │
│  │ ├─ daily/      │  │ ├─ memsearch  │  │ agents/      │               │
│  │ ├─ domains/    │  │ ├─ state.json │  │ commands/    │               │
│  │ ├─ entities/   │  │ ├─ push-queue │  │ hooks/       │               │
│  │ ├─ signals/    │  │ └─ logs       │  │ tools/       │               │
│  │ ├─ plans/      │  │               │  │              │               │
│  │ ├─ sessions/   │  │               │  │              │               │
│  │ ├─ USER.md     │  │               │  │              │               │
│  │ └─ MEMORY.md   │  │               │  │              │               │
│  └────────────────┘  └───────────────┘  └──────────────┘               │
│                                                                        │
└──────────────┬─────────────────────┬────────────────┬──────────────────┘
               │                     │                │
               ▼                     ▼                ▼
      ┌────────────────┐   ┌──────────────────┐   ┌────────────┐
      │ Codex OAuth    │   │   Notion         │   │ iMessage   │
      │ (GPT-5.2-codex)│   │   (task·cal)     │   │ (via Hermes│
      │                │   │                  │   │  iMessage  │
      │                │   │                  │   │  adapter)  │
      └────────────────┘   └──────────────────┘   └────────────┘
                                                        │
                                                        ▼
                                              사용자 (iPhone · Mac)
```

---

## 3. Identity Layer 상세

Hermes는 부팅 시 **프로젝트 루트에서 3개 identity 파일을 자동 탐지**하여 시스템 프롬프트에 주입한다.

| 파일 | 역할 | 위치 | 편집 주체 |
|---|---|---|---|
| `SOUL.md` | 인격 · 톤 · 금지사항 · 기본 행동 | 루트 (commit) | 사용자 (드물게) |
| `AGENTS.md` | 스킬 라우팅 · 관례 · 경계 · 도구 허용 | 루트 (commit) | 사용자 + 업데이트 |
| `USER.md` | 사용자 프로필 (학습 + 수동) | 루트 symlink → `brain/USER.md` | 시스템 학습 + 사용자 편집 |

**symlink**: `USER.md` → `brain/USER.md`. Hermes는 루트에서 파일을 읽지만, 실제 데이터는 `brain/`에 위치. 이식성·백업 일원화.

**시스템 프롬프트 조립 순서** (Hermes 표준):
1. SOUL.md (고정 인격)
2. AGENTS.md (프로젝트 규약)
3. USER.md (사용자 맥락)
4. Active agent persona (있을 때)
5. Relevant skills (on-demand 로드, progressive disclosure)
6. Current task context

---

## 4. Knowledge Layer 상세

### 4.1 Skills (knowledge) — `skills/`

- **Progressive disclosure**: description만 항상 로드, SKILL.md 본문은 trigger 매치 시 로드
- **Nested 구조 지원**: `skills/morning-brief/SKILL.md`, 참조 파일은 선택적 로드
- **자동 승격**: Hermes가 반복 패턴 감지 시 스킬 초안 생성 (승인 필요)

### 4.2 Memory Index — `brain/MEMORY.md`

Hermes가 자동 인덱스로 활용. brain/의 주요 폴더 맵 + 최근 중요 이벤트 요약.

### 4.3 Actual Knowledge — `brain/*`

사용자 데이터. memsearch가 인덱싱. MCP 도구로 mcs가 접근.

---

## 5. Execution Layer 상세

### 5.1 Skills (auto-triggered) — `skills/`

각 스킬은 폴더 + SKILL.md:
```
skills/morning-brief/
├── SKILL.md              ← frontmatter (description, trigger, tools, model) + 지침
└── template.md           ← 참조 파일 (필요 시만 로드)
```

### 5.2 Agents (personas) — `agents/`

각 agent는 단일 .md:
```
agents/tutor-english.md
---
name: tutor-english
description: English conversation session runner
tools: [memory, llm, hermes]
model: ollama-local
isolation: fork            ← 자체 컨텍스트
---
(페르소나 설명)
```

"Workflow" 개념은 agent로 흡수. 영어 회화 session = tutor-english agent가 실행하는 한 세션.

### 5.3 Commands (explicit) — `commands/`

명시 호출 entry point. 사용자가 `/brief`, `/english` 등으로 호출.
```
commands/english.md
---
name: english
description: Start English conversation session
agent: tutor-english       ← 대응 agent 지정
---
```

### 5.4 Tools (capabilities) — `tools/`

Python 모듈. 외부 시스템당 1개:
| Tool | 스코프 |
|---|---|
| `notion.py` | Notion DB·캘린더 read/write |
| `memory.py` | brain/ 검색·저장·엔티티 |
| `llm.py` | Codex OAuth + Ollama 라우팅 |
| `hermes.py` | Hermes 브리지 (subagent·메시지) |
| `file.py` | brain/ 파일 조작 |

### 5.5 Hooks (lifecycle) — `hooks/`

MVP는 2 타입만:
- **command**: 셸 스크립트 실행 (감사 로깅)
- **agent**: subagent 태스크 (복잡한 검증)

향후 확장: http (webhook), prompt (메타-LLM 평가).

---

## 6. Platform Layer

### 6.1 Hermes Runtime

- 버전: v0.7.x 고정 (API 안정성)
- 위치: `~/.hermes/`
- 핵심 기능 활용:
  - **nested skills**: 우리 `skills/`를 그대로 인식
  - **multi-agent (subagent)**: 우리 `agents/` 실행
  - **iMessage adapter**: 네이티브 내장 (AppleScript)
  - **내장 cron**: launchd 불필요
  - **MCP client**: mcs 서버 접근
  - **Profile**: MVP 싱글 (향후 확장 대비)

### 6.2 Hermes Config (`~/.hermes/config.yaml`)

```yaml
profile: magic-conch-shell
skills:
  - ~/magic-conch-shell/skills
subagents:
  - ~/magic-conch-shell/agents
hooks:
  - ~/magic-conch-shell/hooks
context_files:
  - ~/magic-conch-shell/SOUL.md
  - ~/magic-conch-shell/AGENTS.md
  - ~/magic-conch-shell/USER.md      # symlink → brain/USER.md
mcp_servers:
  mcs:
    transport: stdio
    command: python ~/magic-conch-shell/mcp/mcs-server.py
platforms:
  - imessage
llm:
  primary: codex-oauth
  fallback: ollama-local
cron:
  - { schedule: "0 7 * * *",  command: "/brief" }
  - { schedule: "0 22 * * *", command: "/retro" }
  - { schedule: "0 20 * * 0", command: "/weekly" }
```

### 6.3 Ollama (Local LLM)

- 버전: **0.21+** (MLX runner 안정화)
- Port: `*:11434` (Tailscale·LAN 접속 가능하도록 `OLLAMA_HOST=0.0.0.0:11434`)
- 환경: `OLLAMA_USE_MLX=1` — MLX backend 활성화
- 모델: **qwen3.6:35b-a3b-mxfp8** (기본, MoE, MLX 검증됨)
- 임베딩: BGE-M3 (memsearch 호출)
- 관리 방식: [`llm-server-template-ollama`](https://github.com/i-conoclast/llm-server-template-ollama) repo
  - `configs/*.yaml`로 모델 추가·전환
  - `./start.sh <model> --install`로 launchd 자동 시작 등록
  - `brew services`는 `stop` + `disable` 필수 (127.0.0.1 기본 바인딩과 충돌)
- 원격 접속: Tailscale MagicDNS — `http://sora-hub-macmini.tail99b038.ts.net:11434/v1`

---

## 7. Data Layer

### 7.1 brain/ (SSoT)
```
brain/
├── USER.md              ← 사용자 프로필 (symlink 대상)
├── MEMORY.md            ← Hermes가 읽는 메모리 인덱스
├── daily/YYYY/MM/DD.md  ← 날짜별 일지
├── domains/
│   └── {7개 도메인}/
├── entities/
│   ├── people/
│   ├── companies/
│   ├── jobs/
│   ├── books/
│   └── drafts/          ← 승인 대기 엔티티
├── signals/             ← 도메인 미지정 캡처
├── plans/               ← 확정 플랜 이력
└── session-state/       ← agent별 진도·로그
    ├── tutor-english/
    │   ├── state.yaml
    │   └── logs/
    └── ...
```

### 7.2 .brain/ (캐시, 재빌드 가능)
```
.brain/
├── memsearch-db/        ← Milvus Lite
├── state.json           ← 런타임 상태
├── pending-push.jsonl   ← Notion 반영 큐
├── approval-inbox.jsonl ← 승인 대기
├── streak-state.json    ← 오라클 streak 카운터
└── logs/mcs.log
```

---

## 8. Integration Layer (MCP + External)

### 8.1 MCP Server — `mcp/mcs-server.py`

magic-conch-shell이 **MCP 서버로 자신을 노출**. Hermes(또는 다른 MCP 클라이언트)가 접근.

**구현 라이브러리**: [`fastmcp`](https://github.com/jlowin/fastmcp) 2.x — 2026 사실상 표준.

**제공 도구 (MCP tools)**:
- `memory_search`, `memory_capture`, `memory_entities_list`
- `notion_read_db`, `notion_create_page`, `notion_update_page`
- `llm_call` (Codex OAuth or Ollama, 라우팅 내부)
- `file_read`, `file_write`

**구현 예시**:
```python
# mcp/mcs-server.py
from fastmcp import FastMCP
from tools import memory, notion, llm, file

mcp = FastMCP(name="mcs", version="0.1.0")

@mcp.tool()
async def memory_search(query: str, domain: str | None = None, top_k: int = 10) -> list[dict]:
    """Search brain/ with hybrid vector + BM25."""
    return await memory.search(query, domain=domain, top_k=top_k)

# ... other tools

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

자세한 규격은 [01-extension-model.md Section 7](01-extension-model.md).

**전송**: stdio (로컬 동일 기기).
**인증**: 로컬 전용이므로 별도 없음.

### 8.2 외부 서비스

| 서비스 | 용도 | 라이브러리 |
|---|---|---|
| Codex OAuth (GPT-5.3-codex) | 외부 LLM 주 | **`oauth-codex`** (PKCE, async) |
| Ollama (로컬) | 로컬 LLM | HTTP (`httpx` or `ollama` SDK) |
| Notion | 태스크 + 캘린더 | `notion-client` SDK |
| iMessage | 채팅 | Hermes 네이티브 (AppleScript) |
| memsearch | 메모리 검색 | `memsearch` + Milvus Lite (Python SDK) |
| **plan-tracker MCP** | OKR·KR snapshot·history | **FastMCP client (stdio)** |

### 8.3 plan-tracker MCP 통합 (신규)

**경계**: plan-tracker는 OKR·KR의 aggregation·storage·Notion sync를 모두 담당.
magic-conch-shell은 **MCP 클라이언트**로 읽기만.

```
mcs (MCP client) → plan-tracker MCP server (stdio)
   ├─ okr_snapshot_current(domain?)
   ├─ okr_snapshot_history(weeks, domain?)
   ├─ okr_kr_detail(kr_id)
   ├─ okr_kr_list(domain?)
   └─ okr_objective_list()
```

**장애 격리**: plan-tracker MCP 다운 → `tools/okr.py`가 None 반환 →
브리핑·리뷰는 OKR 섹션 없이 graceful degrade.

자세한 규격은 [tech-comparison/00-decisions.md](tech-comparison/00-decisions.md) "plan-tracker 통합 방식" 섹션.

---

## 9. 데이터 플로우 (4가지 주요 경로)

### Flow A: 텍스트 캡처 (FR-A1)
```
사용자 → Hermes (iMessage or CLI)
       → Hermes skill "capture" 호출 (또는 자동 탐지)
       → MCP tool: memory.capture
       → mcs: brain/signals/ or brain/domains/.../...md 저장
       → memsearch live sync → .brain/ 재인덱싱
       → (비동기) Hermes skill "entity-extract" 호출 → 초안 생성 (승인 대기)
```

### Flow B: 아침 브리핑 (FR-D1)
```
Hermes cron 07:00 → /brief 명령
       → Hermes command "brief" → skill "morning-brief" 실행
       → MCP tool: notion.read_db (오늘 태스크·캘린더)
       → MCP tool: memory.search (어제·최근 변화)
       → LLM call (Codex OAuth)
       → 브리핑 생성 → brain/daily/.../DD.md에 저장
       → Hermes iMessage adapter → 사용자에게 전송
       → (사용자 응답 시) skill "plan-confirm" 발동 → 대화
       → 확정 → MCP tool: notion.create_page
```

### Flow C: 저녁 회고 (FR-D3)
```
Hermes cron 22:00 → /retro 명령
       → skill "evening-retro"
       → MCP tool: memory.get_approval_inbox
       → 각 항목 (엔티티 초안·스킬 승격·제안) 대화형 처리
       → 사용자 결정 → brain/ 갱신 or 큐 삭제
       → 하루 회고 텍스트 → brain/daily/.../DD.md 회고 섹션에 append
```

### Flow D: 학습 세션 (FR-E)
```
사용자: "영어 회화 시작" (명시) or 맥락 감지
       → Hermes command /english → agent "tutor-english" 실행 (isolation: fork)
       → agent: MCP tool memory.read_session_state("tutor-english")
       → 지난번 진도 요약부터 시작
       → (대화 N턴, LLM = ollama-local, 민감도 따라 escalation)
       → 세션 종료 → MCP tool memory.save_session_log + state update
```

---

## 10. LLM 라우팅

`tools/llm.py`의 `route()` 함수:

```python
def route(task: TaskType, sensitive: bool = False) -> LLMClient:
    if sensitive:  # finance, relationships, mental, health
        return ollama_local()
    match task:
        case "morning_brief" | "consulting" | "logic_challenge" | "weekly_review":
            return codex_oauth() or ollama_local()
        case "entity_tag" | "summary" | "retro" | "session":
            return ollama_local()
        case "oracle":
            return None  # 사전 조회만, LLM 미사용
```

Fallback 체인: Codex OAuth → Ollama 로컬 → 에러 출력.

---

## 11. Hooks (MVP 2종)

### 11.1 command hook (셸 스크립트)
예: 모든 외부 쓰기 전 감사 로그
```
hooks/command/pre-external-write.sh
  → stdin: JSON (tool·args·sensitive flag)
  → 로그 기록 → exit 0 (진행) or exit 2 (차단)
```

### 11.2 agent hook (subagent 태스크)
예: 확정 플랜 검증을 subagent에 위임
```
hooks/agent/verify-plan.md
  ---
  name: verify-plan
  description: Validate plan coherence before Notion push
  ---
  (검증 로직)
```

---

## 12. 장애 대응

| 외부 | 실패 시 | 복구 |
|---|---|---|
| Ollama | Codex OAuth로 fallback | 자동 재시작 시도 |
| Codex OAuth | Ollama 로컬로 fallback | rate limit 해제 후 자동 복귀 |
| Notion | `.brain/pending-push.jsonl`에 큐잉 | 지수적 backoff 재시도 |
| iMessage / Hermes | 터미널 출력 fallback | Hermes 재시작 |
| memsearch | grep fallback | `mcs reindex` 수동 |
| MCP server | Hermes 직접 실패 보고 | `mcs serve` 재시작 |

---

## 13. 설계 원칙 요약

1. **3-tier**: skills (지식) / agents (퍼소나) / commands (entry). Claude Code 표준.
2. **Identity 레이어 명시**: SOUL·AGENTS·USER 3파일이 시스템 프롬프트 기반.
3. **MCP 표준 통신**: Hermes ↔ mcs는 MCP stdio. 다른 에이전트와도 호환.
4. **Hermes 런타임 재활용**: nested skills·multi-agent·iMessage·cron 모두 내장 기능 활용.
5. **마크다운 SSoT**: brain/이 원본. DB·캐시는 재빌드 가능.
6. **라우팅 중앙**: LLM 선택·승인 인박스·장애 대응 모두 통합 모듈.
7. **Progressive disclosure**: skills/agents는 설명만 기본 로드, 본문은 on-demand.
8. **최소 권한**: 각 skill·agent가 `tools:` 필드로 허용 명시.
9. **Graceful degradation**: 외부 1~2개 실패해도 핵심 루프 지속.
10. **Identity 파일은 보호**: 에이전트가 SOUL·AGENTS 자동 수정 금지.

---

## 다음 문서

- 데이터 구조 상세: [02-data-model.md](02-data-model.md)
- 확장 포인트·프론트매터 표준: [01-extension-model.md](01-extension-model.md)
- FR별 설계: [fr-notes/](fr-notes/)
- 기술 결정 근거: [tech-comparison/](tech-comparison/)
