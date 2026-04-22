# 02. Data Model

**작성일**: 2026-04-19
**최종 갱신**: 2026-04-19 (3-tier + identity + MCP 반영)
**전제**: [00-architecture.md](00-architecture.md), [tech-comparison/00-decisions.md](tech-comparison/00-decisions.md)

---

## 1. 전체 디렉토리 구조

```
magic-conch-shell/                    ← Git 저장소
│
├── SOUL.md                          ← 인격 (Identity)
├── AGENTS.md                        ← 프로젝트 규약 (Identity)
├── USER.md                          ← 사용자 프로필 (symlink → brain/USER.md)
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── config.yaml                       ← mcs 설정 (선택)
│
├── skills/                           ← Knowledge (SKILL.md, auto-triggered)
│   ├── morning-brief/
│   │   ├── SKILL.md
│   │   └── template.md               (참조 파일, 선택)
│   ├── evening-retro/SKILL.md
│   ├── weekly-review/SKILL.md
│   ├── conch-answer/
│   │   ├── SKILL.md
│   │   └── oracle-dictionary.md
│   ├── entity-extract/SKILL.md
│   └── plan-confirm/SKILL.md
│
├── agents/                           ← Subagent personas
│   ├── planner.md
│   ├── oracle.md
│   ├── tutor-english.md
│   ├── tutor-ml.md
│   ├── interviewer.md
│   └── advisor-finance.md
│
├── commands/                         ← Explicit entry points
│   ├── brief.md
│   ├── retro.md
│   ├── weekly.md
│   ├── english.md
│   ├── ml.md
│   ├── mock-interview.md
│   └── finance.md
│
├── tools/                            ← Python 도구 (외부 시스템당 1개)
│   ├── notion.py
│   ├── memory.py
│   ├── llm.py
│   ├── hermes.py
│   └── file.py
│
├── hooks/                            ← Lifecycle hooks (MVP 2종)
│   ├── command/
│   │   └── pre-external-write.sh
│   └── agent/
│       └── verify-plan.md
│
├── mcp/                              ← MCP 서버 (mcs 노출)
│   └── mcs-server.py
│
├── src/mcs/                          ← Python 구현
│   ├── cli.py                        (Typer entry)
│   ├── engine/                       (요청 라우팅)
│   ├── adapters/                     (memsearch·notion-client·codex)
│   └── config/
│
├── templates/                        ← 구조화 기록 템플릿
│   ├── interview-note.md
│   ├── meeting-note.md
│   └── experiment-log.md
│
├── docs/                             ← 설계 문서 (commit)
│   ├── requirements/
│   ├── features/
│   ├── design/
│   └── archive/
│
└── scripts/                          ← 설치·유틸
    ├── install.sh
    └── setup-hermes.sh

brain/                                ← USER DATA (gitignored)
├── USER.md                           ← 사용자 프로필 (symlink 대상)
├── MEMORY.md                         ← Hermes가 읽는 인덱스
├── daily/
│   └── YYYY/
│       └── MM/
│           └── DD.md                 ← 날짜별 통합 일지
├── domains/
│   ├── career/
│   ├── health-physical/
│   ├── health-mental/
│   ├── relationships/
│   ├── finance/
│   ├── ml/
│   └── general/
├── entities/
│   ├── people/
│   ├── companies/
│   ├── jobs/
│   ├── books/
│   └── drafts/                       ← 승인 대기
│       ├── people/
│       ├── companies/
│       └── ...
├── signals/                          ← 도메인 미지정
│   └── YYYY-MM-DD-HHmmss.md
├── plans/                            ← 확정 플랜 이력
│   └── YYYY-MM-DD-{slug}.md
└── session-state/                    ← agent별 진도·로그
    ├── tutor-english/
    │   ├── state.yaml
    │   └── logs/YYYY-MM-DD.md
    ├── tutor-ml/
    ├── interviewer/
    └── advisor-finance/

.brain/                               ← CACHE (gitignored, 재빌드 가능)
├── memsearch-db/                     (Milvus Lite)
├── state.json                        (런타임 상태)
├── pending-push.jsonl                (Notion 반영 큐)
├── approval-inbox.jsonl              (승인 대기)
├── streak-state.json                 (오라클 streak)
└── logs/
    └── mcs.log
```

---

## 2. Identity 3파일

### 2.1 SOUL.md (루트)
- 편집: 사용자 (드물게)
- Hermes 자동 주입
- 내용: 3 Beliefs + style + avoid + defaults
- 실파일 내용은 본 repo `/SOUL.md` 참조

### 2.2 AGENTS.md (루트)
- 편집: 사용자 + 변경 시 업데이트
- Hermes 자동 주입
- 내용: 스킬·agent·command 라우팅, 관례, boundaries, 도구 목록
- 실파일 내용은 본 repo `/AGENTS.md` 참조

### 2.3 USER.md (symlink → brain/USER.md)
- 편집: 시스템 학습 (auto 섹션) + 사용자 수동 (manual 섹션)
- 루트 파일은 symlink, 실제 내용은 `brain/USER.md`
- Hermes 자동 주입
- **구조**:
  ```markdown
  # USER

  ## Identity (manual)
  ## Life Rhythm (auto)
  ## Preferences (auto)
  ## Tone Preferences (auto)
  ## Manual Rules (user-authored)
  ```
- 경계: "Manual Rules" 섹션은 에이전트 수정 금지

---

## 3. Skills 구조 (SKILL.md 표준)

### 3.1 파일 포맷

```markdown
---
name: morning-brief
description: Generate daily morning briefing with today's tasks, yesterday misses, and external signals. Triggered automatically at 07:00 KST.
trigger:
  - cron: "0 7 * * *"
  - command: /brief
tools: [memory, notion, llm, file]
model: codex-oauth
---

# Morning Brief

## When to use
- 매일 07:00 자동 실행
- 사용자가 /brief 호출 시

## Steps

1. 오늘 날짜·요일 확인
2. memory.search로 어제 미완료 · 최근 엔티티 변화 추출
3. notion.read_db로 오늘 예정 태스크·캘린더 가져오기
4. llm.call (codex-oauth)로 브리핑 텍스트 생성
5. file.write로 brain/daily/YYYY/MM/DD.md 저장
6. hermes.send_imessage로 사용자 전송

## Output format

(템플릿 — template.md 참조)

## References
- [template.md](template.md)
```

### 3.2 Frontmatter 필드

| 필드 | 필수 | 설명 |
|---|---|---|
| `name` | ✅ | 고유 이름 (kebab-case) |
| `description` | ✅ | 트리거 매칭 & progressive disclosure용. 150자 이내 권장 |
| `trigger` | ✅ | cron, command, event 중 하나 이상 |
| `tools` | ✅ | 허용 도구 목록 (없으면 빈 배열) |
| `model` | optional | 강제 모델 지정 (기본: 라우터가 결정) |
| `sensitive` | optional | `true`면 로컬 LLM 강제 |
| `max_turns` | optional | 대화 턴 상한 |

### 3.3 Progressive Disclosure 구현

- 기본 컨텍스트: 모든 SKILL.md의 `name` + `description`만 로드
- trigger 매치 시: 해당 SKILL.md 본문 로드
- 본문이 참조 파일 언급 시: bash 등으로 on-demand 로드
- 사용자 경로 포함 시: 해당 폴더 내 다른 .md만 로드 (sandboxing)

### 3.4 자동 승격 (FR-E5)

Hermes가 반복 패턴 감지 시:
1. 초안 생성 → `skills/drafts/{name}/SKILL.md` (신규 폴더)
2. 저녁 회고 승인 인박스에 항목 추가
3. 사용자 승인 → `skills/{name}/`로 이동

---

## 4. Agents 구조

### 4.1 파일 포맷

```markdown
---
name: tutor-english
description: English conversation session runner. Resumes from last session progress.
tools: [memory, llm, hermes]
model: ollama-local
isolation: fork
max_turns: 50
state_path: brain/session-state/tutor-english/
---

# English Tutor

## Persona
You are an English conversation partner. Adapt to user's level.

## Session structure
1. Read last session state from state_path/state.yaml
2. Greet and recap last topic
3. Conversation flow based on user's current level
4. Save progress + today's log to state_path

## Rules
- No Korean translation unless explicitly asked
- Correct grammar gently
- Adjust difficulty based on response quality
```

### 4.2 Frontmatter 필드

Skills 공통 필드 + 추가:

| 필드 | 설명 |
|---|---|
| `isolation` | `fork` (자체 컨텍스트) / `shared` (메인과 공유) |
| `state_path` | 세션 상태 저장 경로 (agent별 분리) |
| `max_turns` | 세션당 대화 턴 상한 |

### 4.3 Session State

agent별 `brain/session-state/{agent-name}/` 디렉토리:
```
brain/session-state/tutor-english/
├── state.yaml              ← 진도
│   ---
│   session_count: 8
│   last_session: 2026-04-15
│   current_topic: Past perfect tense
│   level: intermediate
│   upcoming: Conditional sentences
│   ---
└── logs/
    ├── 2026-04-15.md       ← 회차별 대화 요약
    └── 2026-04-19.md
```

---

## 5. Commands 구조

### 5.1 파일 포맷

```markdown
---
name: english
description: Start English conversation session
agent: tutor-english
---

# /english

Invokes the English conversation tutor agent.

Optional: `/english --new` to reset session state.
```

### 5.2 CLI 대응

Python Typer CLI는 `commands/` 파일들을 읽어 CLI 서브커맨드 자동 등록.
- `/english` (Hermes slash command)
- `mcs english` (Typer CLI)
둘 다 동일 agent 호출.

---

## 6. Tools (Python)

Python 모듈. MCP 서버 `mcp/mcs-server.py`에서 각 도구 등록.

```python
# tools/notion.py
async def read_db(db_id: str, filter: dict = None) -> list[dict]: ...
async def create_page(db_id: str, properties: dict) -> str: ...
async def update_page(page_id: str, properties: dict) -> None: ...
```

```python
# mcp/mcs-server.py
from mcp import Server
from tools import notion, memory, llm, hermes, file

server = Server("mcs")

@server.tool("notion.read_db", "...")
async def notion_read_db(...): ...
```

각 스킬·agent는 `tools: [notion, memory]`로 묶음 선언 → MCP 서버가 해당 네임스페이스 하위 도구 전부 허용.

---

## 7. Hooks 구조 (MVP 2종)

### 7.1 command hook

```
hooks/command/pre-external-write.sh
```

실행 환경:
- stdin: JSON (`tool`, `args`, `sensitive`, `timestamp`)
- exit 0: 진행, exit 2: 차단
- 예: 민감 데이터가 외부 LLM 페이로드에 포함되면 차단

```bash
#!/bin/bash
# stdin JSON 파싱
input=$(cat)
sensitive=$(echo "$input" | jq -r '.sensitive')
tool=$(echo "$input" | jq -r '.tool')

# 로그 기록
echo "$(date -u +%s) $tool sensitive=$sensitive" >> ~/.mcs/hooks.log

# 민감 데이터 + 외부 LLM이면 차단
if [[ "$sensitive" == "true" && "$tool" == "llm.call" ]]; then
  model=$(echo "$input" | jq -r '.args.model')
  if [[ "$model" == "codex-oauth" ]]; then
    echo "blocked: sensitive data to external LLM" >&2
    exit 2
  fi
fi

exit 0
```

### 7.2 agent hook

```
hooks/agent/verify-plan.md
---
name: verify-plan
description: Validate plan coherence before Notion push
tools: [memory]
---

# Verify Plan

Given a confirmed plan, check:
1. Does it conflict with today's calendar?
2. Does it align with stated KR priorities?
3. Any logical inconsistency?

Return: ok | warn(reason) | block(reason)
```

Hermes가 trigger 시점(pre-push)에 이 agent를 subagent로 실행, 결과를 받아 진행/중단 결정.

---

## 8. brain/ 세부 구조

### 8.1 USER.md
이미 Section 2.3에서 정의. 자동 + 수동 구분.

### 8.2 MEMORY.md

Hermes가 읽는 인덱스. 요약 + 포인터.

```markdown
# Memory Index

## Recent Highlights
- 2026-04-19: Anthropic MLE 1차 면접 (people/jane-smith)
- 2026-04-18: ML 공부 세션 7회차 (Attention mechanism)

## Active Entities
- people/jane-smith — 최근 3회 접촉
- companies/anthropic — 지원 진행 중
- jobs/anthropic-mle — interviewing

## Active Workflows (session-state/)
- tutor-english: 8회차, Past perfect
- tutor-ml: 12회차, LoRA fine-tuning

## Key User Rules (from USER.md)
- 주말 재무 챌린지 비활성화
- 가족 관련 제안은 저녁 회고로
```

**자동 갱신**: mcs가 주 1회 `brain/MEMORY.md`를 재생성.

### 8.3 daily/YYYY/MM/DD.md

하루 통합 파일. 브리핑 + 엔트리 + 회고 한 파일:

```markdown
---
id: 2026-04-19
type: daily
date: 2026-04-19
sections: [brief, entries, retro]
---

## 🌅 Morning Brief (07:15)
...

## 📝 Entries (시간순)
- 08:32 [[domains/career/2026-04-19-morning-reflection]]
- 14:45 [[signals/2026-04-19-144530]]

## 🌙 Evening Retro (22:30)
...
```

### 8.4 domains/ — 7 도메인
```
brain/domains/career/2026-04-19-anthropic-mle-1st-round.md
```

프론트매터:
```yaml
---
id: 2026-04-19-anthropic-mle-1st-round
type: note
domain: career
entities: [people/jane-smith, companies/anthropic, jobs/anthropic-mle]
created_at: 2026-04-19T14:22:00+09:00
source: typed
tags: [interview, feedback]
---
```

### 8.5 entities/
각 엔티티 타입별 폴더. 세부는 Section 9.

### 8.6 signals/
도메인·타입 미지정 자동 캡처. slug: `YYYY-MM-DD-HHmmss.md`.

### 8.7 plans/
확정 플랜 이력. Notion push 결과 `notion_page_id` 저장.

### 8.8 session-state/
agent별 진도. Section 4.3에서 정의.

---

## 9. 엔티티 모델

### 9.1 People 템플릿

```markdown
---
kind: people
slug: jane-smith
name: Jane Smith
role: ML Recruiter
company: companies/anthropic
relation: professional
first_met: 2026-03-12
last_contact: 2026-04-10
next_followup: 2026-04-25
---

## Context
Anthropic MLE 포지션 리쿠르터.

## Recent
- 2026-04-10: 1차 기술 인터뷰 피드백
- 2026-03-28: 리쿠르터 콜

## Next actions
- 2026-04-25: Follow-up 메일 예정

## Back-links (auto)
<!-- AUTO-GENERATED BELOW. DO NOT EDIT. -->
- [[domains/career/2026-04-19-anthropic-mle-1st-round]]
- [[domains/career/2026-04-10-jane-feedback]]
<!-- END AUTO-GENERATED -->

## Manual notes
(사용자 편집 영역)
```

### 9.2 Companies·Jobs·Books

비슷한 구조. 각 타입별 필드는 이전 02-data-model 원본 참조 (02-data-model의 Section 5 그대로 유지).

### 9.3 Drafts 워크플로

```
brain/entities/drafts/people/jane-smith.md
```

- 프론트매터에 `status: draft` + `promoted_from: signals/...`
- 저녁 회고에서 승인 시 `brain/entities/people/`로 이동
- 거절 시 삭제 + `.brain/rejected-entities.log` 기록

---

## 10. .brain/ 캐시

### 10.1 memsearch-db/
Milvus Lite 관리. 건드리지 않음. `mcs reindex`로 재빌드.

### 10.2 state.json
```json
{
  "last_sync_at": "2026-04-19T22:30:15+09:00",
  "last_morning_brief_at": "2026-04-19T07:15:00+09:00",
  "pending_approvals": 3,
  "watcher_pid": 12345,
  "hermes_status": "running"
}
```

### 10.3 pending-push.jsonl
Notion 반영 대기 큐. 지수적 backoff로 재시도.

### 10.4 approval-inbox.jsonl
저녁 회고 승인 대기.

### 10.5 streak-state.json
오라클 톤 연속 응답 추적 (FR-F4).

---

## 11. Slug·명명 규칙

| 대상 | 포맷 | 예 |
|---|---|---|
| 타이핑 노트 | `YYYY-MM-DD-{kebab-title}` | `2026-04-19-anthropic-mle-1st-round` |
| 자동 생성 | `YYYY-MM-DD-HHmmss` | `2026-04-19-142230` |
| 사람 | `{firstname-lastname}` | `jane-smith` |
| 회사 | `{company-name}` | `anthropic` |
| 직무 | `{company}-{role-kebab}` | `anthropic-mle` |
| 책 | `{title-kebab}` + `-{author}` | `designing-ml-systems-chip-huyen` |
| 세션 로그 | `YYYY-MM-DD` | — |

**충돌 처리**: `-2`, `-3` suffix. 한글 slug 허용 (자동 생성은 영어 우선).

---

## 12. 프론트매터 스펙 요약

모든 brain/ 마크다운은 YAML 프론트매터 필수.

공통:
```yaml
id: {slug}
type: note | signal | daily | retro | plan | entity-ref | session-log | user-model
created_at: ISO 8601 +09:00
updated_at: ISO 8601 +09:00
source: typed | chat | file-watcher | hermes-generated | auto-promoted
```

타입별 추가 필드는 각 Section 참조 (`note`는 Section 8.4, `entity-ref`는 Section 9, `session-log`는 Section 4.3).

---

## 13. Git 전략

```
.gitignore:
brain/
.brain/
.env
*.log
__pycache__/
.venv/
```

**커밋되는 것**: 코드, 설계 문서, skills·agents·commands·tools·hooks 정의, SOUL.md, AGENTS.md, USER.md **symlink 자체**.

**커밋되지 않는 것**: `brain/` 내용 (user data), `.brain/` (캐시).

**사용자 선택**: `brain/`를 별도 private git repo로 백업할 수 있음.

---

## 14. 주요 설계 결정

1. **3-tier 분리**: skills / agents / commands 각자 역할
2. **Identity 3파일**: SOUL + AGENTS + USER (symlink)
3. **마크다운 + YAML 프론트매터** 전역
4. **SKILL.md 폴더 구조**: 참조 파일 함께 둘 수 있음
5. **Agent isolation: fork**: 자체 컨텍스트로 세션 격리
6. **Tool scope = 외부 시스템당 1개**: 세분화 안 함
7. **Hook MVP 2종**: command + agent만
8. **MCP stdio**: 로컬 전용, 인증 불필요
9. **타임존 KST 고정**
10. **brain/USER.md + 루트 symlink** — Hermes 호환성 + 데이터 일원화

---

## 다음 문서

- 확장 포인트·프론트매터 상세 규격: [01-extension-model.md](01-extension-model.md)
- FR별 설계: [fr-notes/](fr-notes/)
- 기술 비교: [tech-comparison/](tech-comparison/)
