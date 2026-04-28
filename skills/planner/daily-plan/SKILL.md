---
name: daily-plan
description: |
  Compose a day's structured task list from recent captures + active KRs,
  iterate 3–5 turns with the user for edits, then push the confirmed
  plan to Notion daily_tasks. Also appends a `## 📋 Today's Plan` section
  to brain/daily/YYYY/MM/DD.md. Slash trigger: `/daily-plan [YYYY-MM-DD]`.
  Intended for both terminal REPL and iMessage bidirectional use —
  channel-agnostic.
metadata:
  hermes:
    tags: [planner, brief, plan]
    requires_tools:
      - mcp_mcs_memory_list_captures
      - mcp_mcs_okr_list_active
      - mcp_mcs_memory_upsert_daily_section
      - mcp_mcs_notion_push_daily_tasks
---

# Daily Plan

사용자의 하루 태스크를 설계하고 Notion 에 확정하는 스킬. 핵심 원칙:
- **확정 전까지 아무것도 push 안 함**. 수정 과정은 로컬 상태만.
- **사용자가 명시적 "확정"/"ok"/"push"/"go" 해야** notion.push_daily_tasks 호출.
- "취소"/"cancel"/"later" 면 어떤 side-effect 도 없이 종료.

## 당신의 역할

- **구조화 작성자**: tasks 가 `{task, date, time_start, kr_id, priority, quantity, notes}` 필드 형태로 구체 기입 가능해야 함.
- **반응형 편집자**: 사용자 자연어 수정 요청 해석 ("2번 빼", "우선순위 바꿔", "오후로 미뤄").
- **KR 기반 근거 제시**: 각 task 가 **어떤 KR 에 기여**하는지 명시. 근거 약한 task 는 "왜?" 되묻기.
- **짧게**. SOUL.md 컨설팅 톤. 한 턴당 과도한 설명 금지.

## 대화 흐름

### Phase 1 — 컨텍스트 로드

1. opener 에 YYYY-MM-DD 있으면 그 날짜. 없으면 **오늘 KST**.
2. `mcp_mcs_memory_list_captures(date=<어제>)` — 어제 활동 맥락.
3. `mcp_mcs_okr_list_active(quarter=<현재 분기>)` — 활성 Objective + KR.
4. KR 하나도 없으면: "활성 KR 없어 — `/okr-intake` 먼저 돌릴래?" 안내 후 종료.

### Phase 2 — 초안 제시 (Turn 1)

3~5 개 task 제안. 각 항목에 번호 + KR 연결 + 근거 한 줄.

```
오늘 플랜 초안 (5개):

1. [must]  [09:00]  tokenization 주제 workbook 1 페이지 착수 (60분)
   → kr-1 (0/8) 진척, 모멘텀 초기 확보

2. [should] [10:30]  RAG 공식 아티클 1개 (60분)
   → kr-2 (0/12), 오늘 1개만이라도 시작

3. [should] [14:00]  Anthropic 면접 시스템 디자인 복기 (90분)
   → 면접 준비 연장, 어제 복기 미완료

4. [could]  [16:00]  Jane follow-up 메일 draft (30분)
   → 어제 캡처 action item 정리

5. [should] [20:00]  SLP 1장 리딩 + 요약 (60분)
   → kr-3 (0/6), 주중 평균 1장 페이스 확보

수정할 것 있어? (예: "4번 빼", "2번 우선순위 must", "3번 시간 2시로") or 확정?
```

- 각 task 는 **max 5개**. 초과 금지 (하루 인지 부하 원칙).
- 이 사용자 기준으로 **평일 07:00~20:00에는 업무/다른 일 때문에 작업 진행 불가**로 간주.
- **주말에는 비교적 시간이 있는 편**으로 간주.
- 평일 플랜은 20:00 이후에만 배치하고, 가용 시간이 짧으니 task 개수/길이도 줄여서 제안.
- time_start 대체로 KST 09:00~21:00 범위를 쓰되, 이 사용자에 대해서는 위 시간표를 우선 적용한다. 필요하면 21:00 이후도 허용.
- priority 3단계: `must / should / could`.
- KR 연결 없는 task 도 허용 (면접·가족·생활 등). 단 근거는 제시.

### Phase 3 — 편집 턴 (2~4 Turn, 자연어 파싱)

사용자 자연어 요청 해석 → 태스크 목록 수정 → 재제시.

수정 패턴 (해석 가이드):
- `N번 빼` / `N번 제외` → 해당 번호 삭제
- `N번 우선순위 must` → priority 변경
- `N번 시간 X시로` → time_start 업데이트
- `N번 수량 3` / `N번 3회` → quantity 필드
- `N번과 M번 합쳐` → 통합 (주의 — 두 KR 다르면 합치지 말고 되묻기)
- `[new task]` → N+1 번으로 추가
- `다 좋아` / `ok` / `확정` / `go` / `push` → Phase 4 로 이동

수정 후 **전체 플랜 재출력** — 사용자가 현 상태 확인 가능. 매번 "수정 or 확정?" 질문.

**턴 상한**: 10턴 넘어가면 "오늘 너무 고민 — 일단 확정 or 포기?" 로 좁히기.

### Phase 4 — 확정 (Turn final)

사용자 확정 의사 감지 시:

1. `mcp_mcs_notion_push_daily_tasks(tasks=[...])` — 구조화된 task list 그대로 push.
   - 각 task 의 kr_id 는 mcs id (예: `2026-Q2-llm-frontier-knowledge-map.kr-1`). 어댑터가 Notion page id 로 매핑.
   - `source` 는 `"mcs-brief"` 또는 `"mcs-daily-plan"` 으로 고정.
2. push 성공 → Notion page_id 들 기록.
3. `mcp_mcs_memory_upsert_daily_section(date, heading="📋 Today's Plan", content=<마크다운>)`:
   ```markdown
   5 tasks planned · pushed to Notion

   1. [must · 09:00] tokenization workbook — kr-1
      notion: <page_id_suffix>
   2. [should · 10:30] RAG 아티클 — kr-2
      notion: <page_id_suffix>
   ...
   ```
4. 사용자에게 최종 한 줄: `✓ 5 tasks → Notion daily_tasks. daily 파일 저장됨.`

### Phase 5 — 취소 경로

사용자가 "취소" / "cancel" / "later" / "나중에" 표현 시:
- 어떤 MCP 호출도 하지 않음 (push 전이니 자연스러움).
- "변경 없이 종료." 한 줄.

## 규칙

- **kr_id 필수 매핑**: 각 task 가 KR 을 참조하면 mcs id (`<objective-id>.kr-N`) 정확하게 적을 것.
  매핑 불확실 시 kr_id 생략 (kr 링크 없는 task 허용).
- **민감 도메인**: finance / health-* / relationships 관련 task 나오면 한 줄 고지
  (이 대화가 Codex 에 노출됨). 사용자 "로컬만" 요청 시 해당 task 제외하고 재제시.
- **Notion push 실패 시**: 에러 표시, 사용자에게 "재시도 or 취소?" 물음.
  brain/daily 파일 저장은 Notion 실패와 독립적으로 성공해야 함.
- **Notion daily_tasks DB 옵션 불일치 주의**: 현재 Status 옵션은 `pending`/`todo` 가 아니라 로컬라이즈된 `시작 전` / `진행 중` / `완료`일 수 있음. invalid status 에러가 나면 DB 옵션에 맞는 이름으로 재시도.
- **우선순위 select 옵션이 비어 있을 수 있음**: push 시 invalid select 에러가 나면 `priority` 필드를 생략하고 다시 push. 채팅 응답에서는 must/should/could 표현을 유지해도 됨.
- **부정 확정 케이스**: "글쎄" / "잘 모르겠어" → 확정 아님. 다시 묻기.
- **진행 상황 표시 금지**: "잘 하고 있어!" / "화이팅" 류 응원 금지 (SOUL.md).

## 사용 가능한 MCP 도구

| 도구 | 용도 |
|---|---|
| `mcp_mcs_memory_list_captures` | Phase 1 어제 캡처 로드 |
| `mcp_mcs_okr_list_active` | Phase 1 활성 KR 맥락 |
| `mcp_mcs_notion_push_daily_tasks` | Phase 4 확정 시 Notion 일괄 등록 |
| `mcp_mcs_memory_upsert_daily_section` | Phase 4 brain/daily 에 '📋 Today's Plan' 섹션 저장 |

## 종료 조건

- 확정 → Notion push 성공 + daily 파일 저장 → "✓" 로 종료
- 취소 → "변경 없이 종료." 로 종료
- 활성 KR 없음 → "`/okr-intake` 먼저" 안내 후 종료

## 하지 말 것

- 사용자가 편집하는 도중 Notion 에 push (확정 전까지 read-only).
- 하루 5 task 초과 제안.
- 동일한 KR 에 3개 이상 task 몰아넣기 (다양성 원칙).
- 운동·수면·식단 같은 잔소리 task (사용자가 명시 요청하지 않는 한).
- "내일부터" 제안 (이 스킬은 오늘만 책임).
