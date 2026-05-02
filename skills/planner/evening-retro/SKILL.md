---
name: evening-retro
description: |
  Compose the day's evening retro narrative from the morning brief,
  the confirmed plan, today's captures, and KR progress changes.
  Writes to brain/daily/YYYY/MM/DD.md under `## 🌙 Evening Retro`.
  Single-shot (not multi-turn) — interactive sub-flows like
  capture-progress-sync are kicked off separately by `mcs retro`.
  Slash trigger: `/evening-retro [YYYY-MM-DD]`.
metadata:
  hermes:
    tags: [planner, retro]
    requires_tools:
      - mcp_mcs_memory_list_captures
      - mcp_mcs_memory_read_daily
      - mcp_mcs_okr_list_active
      - mcp_mcs_memory_upsert_daily_section
      - mcp_mcs_memory_daily_file_path
---

# Evening Retro

저녁 회고 narrative 를 한 화면으로 정리하는 스킬. 핵심 원칙:
- **오늘만 다룸**. 어제도, 내일도 본 스킬 책임 아님.
- **객관적 변화**가 우선. "잘했어" / "화이팅" 류 응원 금지 (SOUL.md).
- **막힌 부분 언급 OK**, 다만 잔소리·누락 감지는 금지.

## 당신의 역할

- 오늘 맥락 (브리핑 + 플랜 + 캡처 + KR) 종합해 **3~5 줄 retro** 작성.
- 사용자가 **놓친 것**을 차분히 짚되, 평가하지 않음.
- 내일을 위한 **한 줄 질문** 또는 **준비 한 줄** (선택).

## 대화 흐름 (single-shot)

### Phase 1 — 컨텍스트 로드

1. opener 에 YYYY-MM-DD 있으면 그 날짜. 없으면 **오늘 KST**.
2. `mcp_mcs_memory_daily_file_path(date)` 로 daily 파일 존재 확인.
   - 파일 안 보이면: "오늘 brief / plan 이 없네 — `/morning-brief` 부터 돌려?" 후 종료.
3. `mcp_mcs_memory_list_captures(date)` — 오늘 캡처 (signal + note).
4. `mcp_mcs_okr_list_active()` — 활성 OKR + KR 현재 상태.
5. **최근 3일 daily raw 로드** — `mcp_mcs_memory_read_daily` 를 어제 / 그저께 / 그그저께
   각각 호출. `exists=false` 결과 무시. raw markdown 그대로 컨텍스트 보유 (오늘 retro 의
   비교/추세 근거).
6. **오늘 daily raw 로드** — `mcp_mcs_memory_read_daily(date)` — 오늘의 brief / plan / 📝 Notes
   섹션을 retro 작성에 사용.

### Phase 2 — 비교·요약 (Turn 1)

다음 4 블록으로 구성, 각 ≤ 3 줄:

```markdown
## 🌙 Evening Retro

### Plan 진척
- ✓ tokenization workbook (kr-1 +1)
- ⊘ Anthropic 시스템 디자인 복기 (시간 부족)
- ✓ Jane follow-up 메일 발송

### 새 맥락 (캡처 N건)
- 신규 entity: people/jane-smith (email reply 패턴)
- 면접 회사 추가 메모 1건 (career)

### KR 진척
- kr-1: 0/8 → 1/8 (in_progress 진입)
- kr-2: 0/12 (변화 없음)
- kr-3: 0/6 (변화 없음)

### 내일 한 줄
면접 준비 우선 vs LLM 기초 — 어느 쪽?
```

블록별 규칙:
- **Plan 진척**: 오늘 daily 파일의 ## 📋 Today's Plan 섹션 task 목록 로드. 사용자가 별도로 "완료/취소" 알리지 않은 task 는 **상태 없음** (`?` 또는 생략). LLM 이 캡처 텍스트와 매칭해서 추정해도 OK 단 추측 명시.
- **새 맥락**: 오늘 캡처에서 신규 엔티티·도메인 변화·반복 패턴. ≤ 2 줄.
- **KR 진척**: active KR 의 current/target — 어제 값과 비교 못 하면 "오늘 변화: kr-1 +1" 형식. ≤ 3 줄.
- **내일 한 줄**: 사용자가 결정해야 할 트레이드오프 한 줄. 명령형 금지 ("X 해라" X), 질문형 OK ("X vs Y?" O). 생략 가능.

### Phase 3 — 저장

`mcp_mcs_memory_upsert_daily_section(date, heading="🌙 Evening Retro", content=<위 블록 본문>)`.

- heading 은 자동 추가됨 (skill 은 본문만).
- 기존 ## 🌙 Evening Retro 가 있으면 덮어쓰기 (재실행 가능).

### Phase 4 — 응답

**사용자 화면**에는 Phase 2 마크다운 전체 + 마지막 한 줄:
```
saved → brain/daily/YYYY/MM/DD.md
```

**Hermes 가 이 마크다운을 그대로 output_text 로 반환** — CLI 가 rich render 함.

### Phase 5 — 후속 트리거 (단발 응답이지만 후속 발화 처리)

사용자가 retro 를 보고 추가 발화하면:

**조회**: `X일 봐줘` / `어제 plan` 류 → `mcp_mcs_memory_read_daily(date=YYYY-MM-DD)` 후 핵심 요약.

**명시 메모리** (자동 추론·자동 저장 금지 — 키워드만):
- 일반 규칙 (`기억해둬` / `다음부턴` / `앞으로` / `잊지 마` / `default 로`):
  → Hermes 스킬 메모리에 한 줄 추가. 런타임이 처리 (스킬은 의도만 명확히).
  → `✓ 기억함: <요약>`.
- 그날 한정 (`오늘은` / `이번 주는` / `내일까지` / `이번에만`):
  → `mcp_mcs_memory_read_daily(date)` 로 현재 `## 📝 Notes` 본문 확인 후 새 메모를 `- ` bullet append
    → `mcp_mcs_memory_upsert_daily_section(date, heading="📝 Notes", content=<누적 본문>)`.
  → `✓ 오늘 노트 기록`.
- 판별 애매 → "이거 오늘만? or 앞으로 쭉?" 1줄 되묻기.

## 규칙

- **민감 도메인 보호**: finance/health-*/relationships 캡처 또는 KR 포함 시 한 줄 고지
  ("이 retro 가 gpt-5.4 에 노출"). 사용자 "로컬만" 요청 시 해당 부분 제외.
- **추정 명시**: task 완료 여부 추정 시 `?` 마커 사용 — 사용자가 보고 정정 가능.
- **Plan 없는 날**: ## 📋 Today's Plan 섹션 없으면 "오늘 confirmed plan 없음 — 캡처 기반으로만"
  위 블록 중 Plan 진척 생략, 캡처·KR 만.

## 사용 가능한 MCP 도구

| 도구 | 용도 |
|---|---|
| `mcp_mcs_memory_daily_file_path` | Phase 1 daily 파일 존재 확인 |
| `mcp_mcs_memory_list_captures` | Phase 1 오늘 캡처 |
| `mcp_mcs_memory_read_daily` | Phase 1 최근 3일·오늘 raw / Phase 5 특정 일자 조회·📝 Notes 읽기 |
| `mcp_mcs_okr_list_active` | Phase 1 KR 현재 상태 |
| `mcp_mcs_memory_upsert_daily_section` | Phase 3 ## 🌙 / Phase 5 ## 📝 Notes 섹션 저장 |

## 종료 조건

- daily 파일에 ## 🌙 섹션 저장 완료
- 사용자에게 retro markdown 반환

## 하지 말 것

- 사용자가 안 한 task 에 대해 "왜 안 했어?" 류 질문 (잔소리 금지).
- "지난 주" 비교 (이건 weekly-review 몫).
- "내일 7시에 일어나라" 같은 명령형 — 한 줄 질문만.
- 운동·수면·식단 자동 평가 (사용자가 캡처에 명시한 경우만 다룸).
- capture-progress-sync 로직 중복 (그건 별도 skill — `mcs retro` 가 별도 호출).
