# magic-conch-shell — SPEC v0.1

> "The shell has spoken."

Personal life brain + daily planner. Built on Hermes Agent, feeds plan-tracker, lives on the Mac mini hub, answers to you.

---

## 1. Vision

**One-liner**: magic-conch-shell은 당신의 전 삶(커리어·건강·ML·관계·재무)을 기억하고, 매일 당신과 대화하며 플랜을 확정해주는 개인 라이프 OS. 진지한 질문엔 brain 데이터 기반으로 답하고, 가벼운 질문엔 소라고둥처럼 장난친다.

**3가지 신념**
1. **Markdown is the source of truth.** DB는 캐시일 뿐. `.md` 날리면 재빌드.
2. **Entities are first-class.** 사람·회사·직무·책은 파일로 존재.
3. **Brain ≠ Tracker.** magic-conch-shell은 해석·대화·플래닝 생성. plan-tracker는 실행 측정.

---

## 2. Scope

### IN (magic-conch-shell의 책임)
- Raw 입력 수집: 타이핑 메모·iPhone 보이스메모·signal capture
- 엔티티 추출·관리 (사람·회사·직무·책)
- 하이브리드 검색 (vector + keyword + RRF)
- 매일 브리핑·회고·넛지 생성
- iMessage 대화형 플래닝 확정
- 확정된 태스크를 plan-tracker/Notion에 push
- Hermes 3-layer memory (skill·conversation·user model)

### OUT (다른 시스템이 함)
- KR 집계·검증·리포트 → **plan-tracker**
- 6 data source 수집 (GitHub·Linear·LeetCode·Claude Code·Git·Notion 기존 수집) → **plan-tracker**
- 공식 대시보드 → **plan-tracker Streamlit**
- SSoT 공식 기록 → **Notion**

---

## 3. System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Mac mini hub (24/7, Qwen3 via mlx-lm)                      │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │  magic-conch-shell (Python + uv)                   │     │
│  │                                                    │     │
│  │  ┌─────────────┐        ┌─────────────────────┐   │     │
│  │  │   BRAIN     │───────▶│     PLANNER         │   │     │
│  │  │             │        │                     │   │     │
│  │  │ ingest/     │        │ morning-brief       │   │     │
│  │  │ entities/   │        │ evening-retro       │   │     │
│  │  │ search/     │        │ weekly-review       │   │     │
│  │  │ signals/    │        │ nudges              │   │     │
│  │  │ daily/      │        │ conch-answer        │   │     │
│  │  └──────┬──────┘        └──────────┬──────────┘   │     │
│  │         │                          │              │     │
│  │         ▼                          ▼              │     │
│  │  ┌──────────────────────────────────────────┐    │     │
│  │  │  Hermes Agent (skills + 3-layer memory) │    │     │
│  │  │  ~/.hermes/skills/*.md                  │    │     │
│  │  └──────────────────────────────────────────┘    │     │
│  └────────────┬──────────────┬────────────────────────┘     │
│               │              │                              │
│  LLM routing: │              │                              │
│   - Codex OAuth (default)    │                              │
│   - Qwen3 local (mlx-lm)     │                              │
│   - Groq Whisper (transcribe)│                              │
└───────────────┼──────────────┼──────────────────────────────┘
                │              │
     ┌──────────▼────┐   ┌─────▼───────────┐
     │ plan-tracker  │   │  Notion         │
     │ (KR·리포트)   │   │  (DB3 Tasks)    │
     └───────────────┘   └─────────────────┘
                │
                ▼
     ┌───────────────────┐
     │  iMessage / `mcs` │  ← 당신
     └───────────────────┘

INPUT SOURCES:
  - 타이핑: mcs capture "…"
  - iPhone 보이스메모 → iCloud Drive → watcher → Whisper → brain
  - Gmail (취업 관련) → recipe → brain (Phase 2)
  - 이전 plan-tracker 노트 (참조만, 이관 X)
```

---

## 4. Domain Schema (임시, OKR 재정의 후 업데이트)

plan-tracker의 o1~o6 그대로 계승:

| domain | 영역 | plan-tracker OKR |
|---|---|---|
| `career` | 글로벌 리모트 포지션 전환 | o1 |
| `health-physical` | 신체 건강 | o2 |
| `health-mental` | 멘탈 건강 | o3 |
| `relationships` | 관계 | o4 |
| `finance` | 재무 | o5 |
| `ml` | ML 공부·연구 | o6 |
| `general` | 도메인 무관 | — |

각 노트는 frontmatter로 domain 태그:
```yaml
---
id: 2026-04-15-anthropic-interview-followup
domain: career
entities: [people/jane-smith, companies/anthropic, jobs/anthropic-mle]
date: 2026-04-15
type: note
---
```

---

## 5. Entity Schema (1급 시민)

| 엔티티 | 경로 | 언제 만들어지나 |
|---|---|---|
| People | `entities/people/{slug}.md` | 신규 이름 언급시 signal-detector가 자동 생성 |
| Companies | `entities/companies/{slug}.md` | 채용/투자/뉴스 언급시 |
| Jobs | `entities/jobs/{company}-{role}.md` | 지원·관심 등록시 |
| Books | `entities/books/{slug}.md` | 독서·언급시 |

**People 템플릿 예**:
```markdown
---
name: Jane Smith
role: ML Recruiter
company: companies/anthropic
relation: professional
first_met: 2026-03-12
last_contact: 2026-04-10
---

## Context
취업 관련 리쿠르터. Anthropic MLE 포지션 소개.

## Recent
- 2026-04-10: 1차 기술 인터뷰 피드백
- 2026-03-28: 리쿠르터 콜

## Back-links
(자동 생성)
```

모든 노트는 언급된 엔티티를 자동 back-link. **"오늘 Jane한테 연락 안 했네"** 같은 넛지 가능해짐.

---

## 6. Directory Structure

```
magic-conch-shell/
├── SPEC.md                    ← this
├── README.md
├── pyproject.toml             ← uv + Python 3.11
├── .env.example
├── src/
│   └── mcs/
│       ├── cli.py             ← typer CLI entry
│       ├── core/
│       │   ├── ingest.py      ← 입력 파이프라인
│       │   ├── entities.py    ← 엔티티 추출·저장
│       │   ├── search.py      ← memsearch + RRF
│       │   ├── rrf.py         ← GBrain src/core/search/rrf.ts 포팅
│       │   ├── signals.py     ← signal-detector 구현
│       │   ├── notion.py      ← Notion DB3 push client
│       │   ├── imessage.py    ← AppleScript/MCP bridge
│       │   ├── watchers.py    ← iCloud voice memo watcher
│       │   └── whisper.py     ← mlx-whisper transcription
│       └── planner/
│           ├── morning.py
│           ├── evening.py
│           ├── weekly.py
│           ├── voice.py       ← 3-mode selector (Conch/Hybrid/Planner)
│           └── templates/
├── skills/                    ← Hermes skills (magic-conch 쪽 주입)
│   ├── signal-detector.md
│   ├── morning-brief.md
│   ├── evening-retro.md
│   ├── weekly-review.md
│   ├── conch-answer.md        ← 3-mode voice skill
│   ├── voice-ingest.md
│   ├── entity-extract.md
│   ├── plan-confirm.md        ← iMessage 대화 프로토콜
│   └── RESOLVER.md
├── brain/                     ← 실제 데이터 (gitignore, Mac mini 전용 볼륨)
│   ├── daily/2026/04/15.md
│   ├── domains/
│   │   ├── career/
│   │   ├── health-physical/
│   │   ├── health-mental/
│   │   ├── relationships/
│   │   ├── finance/
│   │   ├── ml/
│   │   └── general/
│   ├── entities/
│   │   ├── people/
│   │   ├── companies/
│   │   ├── jobs/
│   │   └── books/
│   ├── signals/               ← raw 캡처 (미분류)
│   └── voice/                 ← 전사 원본
├── .brain/                    ← 캐시 (언제든 재빌드 가능)
│   ├── index.db               ← sqlite+vss or milvus-lite
│   └── state.json
├── tests/
└── docs/
    ├── voice-guide.md         ← 3-mode voice 규칙 문서
    ├── imessage-protocol.md
    └── plan-tracker-contract.md
```

---

## 7. CLI Commands (`mcs`)

```bash
# Ingest
mcs capture "생각 한 줄"              # 즉시 signals/에 저장
mcs capture -d career "…"              # 도메인 지정
mcs ingest <file.md>                   # 파일 ingest
mcs ingest voice <recording.m4a>       # 음성 전사+ingest (수동)

# Search / Query
mcs search "지난달 anthropic 면접"
mcs search --entity people/jane-smith
mcs ask "오늘 Jane한테 follow-up 했나?"  # Mode 1 planner

# Planning
mcs brief                              # on-demand 아침 브리핑 (터미널)
mcs retro                              # 저녁 회고 (대화형)
mcs weekly                             # 주간 리뷰

# Entity ops
mcs entity list people
mcs entity show people/jane-smith
mcs entity link <note> <entity>

# Plan-tracker bridge
mcs push <plan-id>                     # 확정 플랜을 plan-tracker에 push

# Daemon
mcs autopilot start                    # signal-detector + watchers + cron
mcs autopilot stop
mcs autopilot status

# Admin
mcs doctor                             # 상태 점검
mcs reindex                            # .brain/index.db 재빌드
mcs config
```

---

## 8. Hermes Skills (skills/*.md)

| Skill | 언제 발동 | 출력 |
|---|---|---|
| `signal-detector` | 매 메시지/캡처시 | 엔티티·아이디어 자동 추출 → brain 저장 |
| `morning-brief` | cron 07:00 | 오늘 태스크+어제 회고 → iMessage |
| `evening-retro` | cron 22:00 | 대화형 회고 → brain/daily/ |
| `weekly-review` | cron 일요일 20:00 | 주간 요약 → Notion |
| `conch-answer` | `mcs ask` 호출시 | 3-mode voice 라우팅 |
| `voice-ingest` | iCloud watcher 트리거 | 전사 + 도메인 분류 + 엔티티 추출 |
| `entity-extract` | 노트 저장시 | 신규 사람/회사/직무 탐지·파일 생성 |
| `plan-confirm` | 브리핑 응답시 | 대화형 플랜 확정 → Notion push |

각 skill은 **Hermes 포맷 마크다운** (SOUL.md 참조 포함).

---

## 9. Voice Rules (docs/voice-guide.md 요약)

**3-Mode**:
- **Mode 1 Planner (진지)**: OKR/커리어/건강/재무/ML/관계 질문 → 데이터 근거 + 의견
- **Mode 2 Conch (장난)**: 반복/사소함/답 뻔함 → 한 단어/한 줄 (`No.`, `Nothing.`, `Maybe someday.`, `The shell has spoken.`)
- **Mode 3 Hybrid**: 가볍지만 근거 있음 → 근거 1줄 + 소라고둥 한 줄

**안전장치**: Mode 2 같은 답 3회 연속 → Mode 1로 강제 복귀.

**라우터 의사코드** (`planner/voice.py`):
```python
def select_mode(query, brain_hits, conch_streak):
    if conch_streak >= 3:
        return "planner"
    if is_serious_domain(query):
        return "planner"
    if brain_hits and is_light_query(query):
        return "hybrid"
    return "conch"
```

---

## 10. GBrain 차용 모듈 (포팅 목록)

| GBrain (TS) | → magic-conch-shell (Python) | 이유 |
|---|---|---|
| `src/core/search/rrf.ts` | `mcs/core/rrf.py` | Hybrid search의 핵심 |
| `src/core/search/intent.ts` | `mcs/core/intent.py` | entity/temporal/event 쿼리 분류 |
| `src/core/operations.ts` 패턴 | `mcs/core/operations.py` | Contract-first (CLI/MCP 동시 생성) |
| `skills/_brain-filing-rules.md` | `skills/_filing-rules.md` | 공통 filing 규칙 |
| `skills/RESOLVER.md` 포맷 | `skills/RESOLVER.md` | 스킬 라우팅 표 |
| 엔티티 back-link 로직 | `mcs/core/entities.py` | 엔티티 1급 시민 |

**차용 안 함**: PGLite 엔진, postgres-engine, pgvector DDL (→ memsearch/Milvus Lite로 대체), contract CLI 전체, integration recipe 시스템 (Phase 2 고려).

---

## 11. memsearch 통합

- `memsearch index brain/` — 초기 인덱싱
- `memsearch watch brain/` — 파일 변경시 자동 재인덱싱 (autopilot이 띄움)
- 검색 호출: Python SDK로 `memsearch.search(query)` → hits
- **GBrain RRF**를 memsearch 결과 위에 얹어 BM25+vector 결합

---

## 12. plan-tracker Contract (docs/plan-tracker-contract.md)

**Push 방향**: magic-conch-shell → Notion DB3 `Daily Tasks`

필요한 필드 (plan-tracker v2 스키마 기준):
- task title
- domain (o1~o6 매핑)
- related KR (선택)
- due date
- status = `Planned`
- source = `magic-conch-shell`
- confirmed_at (iMessage 대화 완료 시각)

**구현**: `notion-client` Python SDK. plan-tracker와 DB ID 공유 (`.env`에서).

---

## 13. Voice Pipeline (iPhone → brain)

```
iPhone 보이스메모
    ↓ iCloud Drive 자동 sync
~/Library/Mobile Documents/com~apple~VoiceMemos/Recordings/*.m4a
    ↓ watchdog (mcs autopilot)
Whisper (mlx-whisper on Mac mini, 로컬)
    ↓
brain/voice/2026-04-15-143012.txt (원본 전사)
    ↓ voice-ingest skill
  - 도메인 분류
  - 엔티티 추출
  - brain/daily/ 또는 signals/ 배치
```

전사 모델: `mlx-community/whisper-large-v3-turbo` (Mac mini 로컬, 무료).

---

## 14. Roadmap

### MVP — 4주 (1 month)
- Week 1: 스캐폴딩, `mcs capture/ingest/search`, 도메인/엔티티 스키마, memsearch 통합
- Week 2: Hermes 설치, 기본 skills 6개 (signal-detector·morning-brief·evening-retro·conch-answer·voice-ingest·entity-extract), Codex OAuth 연결
- Week 3: iMessage 양방향 (plan-confirm), Notion DB3 push, voice watcher
- Week 4: autopilot cron, GBrain RRF 포팅, 첫 실사용 + 튜닝

### v1.0 — 2~3개월
- Gmail 취업 메일 자동 ingest
- weekly-review skill
- plan-tracker 리포트 연동 (양방향)
- 3-mode voice 튜닝 (Mode 2 사전 확장)
- Skill 자기개선 루프 (Hermes 자체 기능 활용)
- OpenHarness 기반 커스텀 agent loop 연구 (선택)

### Out of MVP
- 별도 대시보드 (나중에 별도 기획)
- 금융 자동 수집
- Apple Health 연동
- 공개 publish 기능

---

## 15. Open Questions (추후 결정)

1. OKR 재정의 시점 — SPEC 확정 후 별도 세션
2. 소라고둥 Mode 2 사전 확장 (원작 대사 + 커스텀 추가?)
3. Notion DB 쓰기 권한 — API key 관리 방식
4. Mac mini에 Hermes 설치시 포트·서비스 관리 (launchd?)
5. brain/ 백업 전략 (로컬 only이지만 최소한 Time Machine? restic?)
6. 엔티티 merge 정책 (동명이인 처리)

---

## 16. Success Criteria (4주 MVP)

- ✅ `mcs capture`로 하루 10건 이상 캡처
- ✅ `mcs brief`가 plan-tracker 데이터 + brain 근거 포함한 아침 브리핑 출력
- ✅ iMessage로 플랜 확정 → Notion DB3에 자동 기록
- ✅ iPhone 음성메모 녹음 → 30분 내 brain/daily/에 전사+분류
- ✅ 3-mode voice가 적어도 정성적으로 구분됨
- ✅ 최소 10개 엔티티 (사람 5 + 회사 3 + 직무 2) back-link 동작

---

The shell has spoken.
