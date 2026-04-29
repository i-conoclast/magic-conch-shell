---
name: capture-progress-sync
description: |
  Walks through a day's captures and proposes capture↔task matches by
  cross-referencing them with today's Notion daily_tasks rows.
  On user approval: creates capture↔task synced relations, transitions
  task Status (시작 전 → 진행 중 / 완료), and bumps the parent KR's
  current when warranted. Intended for evening retro cadence but can be
  invoked ad-hoc for any date. Slash trigger:
  `/capture-progress-sync [YYYY-MM-DD]`.
metadata:
  hermes:
    tags: [planner, okr, progress]
    requires_tools:
      - mcp_mcs_memory_list_captures
      - mcp_mcs_memory_add_task_link
      - mcp_mcs_notion_list_daily_tasks
      - mcp_mcs_notion_update_daily_task_status
      - mcp_mcs_notion_push_capture
      - mcp_mcs_okr_list_active
      - mcp_mcs_okr_update_kr
---

# 캡처 진척 동기화

오늘 만든 capture 들을 같은 날의 daily_tasks 와 묶어 진척으로 반영하는
스킬. 핵심:
- **task 가 1차 연결 대상**. KR 은 task 를 통해 transitive 로 묶임.
- **task 매칭 안 되는 capture** 는 그냥 둠 (옵션 A: KR 직접 링크 안 함).
- 사용자 승인 시점에만 Notion 에 쓰기 (capture.Tasks relation, task.Status,
  필요 시 KR.current).

## 당신의 역할

- **객관 매칭**: capture text + 오늘 task list 비교 → 자연스러운 짝.
- **상태 추정**: 매칭만 되면 task Status `시작 전` → `진행 중`. 사용자가
  "1번 완료" / "task 2 done" 명시하면 → `완료`. 추측으로 `완료` 만들지 말 것.
- **KR 진척**: task 가 `완료` 로 가는 시점에만, 그 task 의 KR 에 `+task.quantity`
  (없으면 +1) 제안. 사용자가 승인하면 `okr.update_kr` 호출.

## 대화 흐름

### Phase 1 — 컨텍스트 로드

1. opener 에 날짜 있으면 그 날짜. 없으면 **오늘 KST**.
2. `mcp_mcs_memory_list_captures(date=<that>)` — 오늘 캡처 목록.
3. `mcp_mcs_notion_list_daily_tasks(date=<that>)` — 오늘 task 목록 (Notion).
4. `mcp_mcs_okr_list_active()` — 활성 KR (kr_id ↔ notion_page_id 매핑용).
5. 캡처 0개 → "오늘 캡처 없음. 끝." 종료.
6. task 0개 → "오늘 plan 도 없음 — `/morning-brief` 부터?" 안내 후 종료.

### Phase 2 — 매칭 제안 (LLM 판단)

각 capture 에 대해 task 후보 0~N 개 제안. 판단 기준:

- **capture text vs task text**: 동사·목적어·수치 일치
- **이미 같은 task 와 link 된 capture 는 스킵** (capture.tasks frontmatter
  또는 task.capture_count 로 확인)
- **domain 일치 가산점**: capture.domain == task 추정 도메인 (KR 의 domain)

제안 형식:
```
capture [c-1] "tokenization workbook 1쪽 완료" (ml)
  → task #2 "tokenization 주제 workbook 1 페이지 착수"
     status 변화 제안: 시작 전 → 진행 중
     (사용자가 "완료" 명시하면 → 완료, kr-1 +1)

capture [c-2] "Anthropic 2차 대비 정리"
  → task #3 "Anthropic 면접 시스템 디자인 복기"
     status 변화 제안: 시작 전 → 진행 중

capture [c-3] "주말 산책"
  → (매칭 없음)
```

근거 짧게. **추측 금지**: capture 가 단순히 KR 도메인이라고 무리하게 task 에
배정하지 말 것. 매칭 부족하면 "(매칭 없음)" 으로 두기.

### Phase 3 — 일괄 승인

전체 제안 후 한 번에 묻기:

```
승인 (전체 y / 번호 1,3 / "1번 완료" / "2번 task 빼" / 취소 n):
```

- `y` / `yes` → 모든 매칭 승인 (status: 시작 전 → 진행 중)
- `n` / `no` / `cancel` / `취소` → 아무 변경 없음, 종료
- `1,3` → 해당 번호만 승인
- `1번 완료` / `task 2 done` → 1번/2번 task 의 status 를 `완료` 로 (KR bump 포함)
- `2번 task 빼` → 그 매칭 제외

### Phase 4 — 반영 (승인된 것만)

각 승인된 (capture, task) 쌍:

1. **capture frontmatter 업데이트**:
   `mcp_mcs_memory_add_task_link(capture_id, task_notion_ids=[task.page_id])`
2. **Notion capture row push**:
   `mcp_mcs_notion_push_capture(capture_id)` — adapter 가 frontmatter 의
   `tasks` 를 Notion `Tasks` relation 으로 보냄
3. **task status 전이**:
   - 사용자가 그 번호에 "완료" 명시 → `완료` 로
   - 그 외, task 가 현재 `시작 전` → `진행 중`
   - 이미 `진행 중` / `완료` 면 그대로
   `mcp_mcs_notion_update_daily_task_status(task.page_id, new_status)`
4. **task 가 방금 `완료` 로 갔으면 → KR bump**:
   - task.kr_notion_id 가 있으면 → 해당 KR 의 mcs id 찾기 (active KR 목록에서 매칭)
   - increment = task.quantity (없으면 1)
   - `mcp_mcs_okr_update_kr(kr_id, fields={"current": <new>})`
   - (이게 자동 Notion KR sync 까지 따라감 — server 가 처리)

상태 옵션 이름: `시작 전`, `진행 중`, `완료` (Notion DB 옵션 그대로). 다른 이름이면
`mcp_mcs_notion_update_daily_task_status` 가 400 에러 — 그 경우 한 줄 보고하고 다음 쌍 진행.

### Phase 5 — 요약

```
✓ 3 매칭 반영:
  capture c-1 → task #2 (시작 전 → 진행 중)
  capture c-2 → task #3 (시작 전 → 진행 중)
  capture c-4 → task #1 (시작 전 → 완료, kr-1 0→1)

매칭 안 된 capture 1건:
  c-3 "주말 산책" (관련 task 없음)
```

## 규칙

- **이미 link 된 쌍 재처리 금지**: capture.tasks 에 task.page_id 가 이미 있으면
  Phase 2 제안에서 제외.
- **capture 가 여러 task 와 매칭 가능**: list 로 줘도 OK.
- **task 가 여러 capture 의 evidence**: 자연스러움. 첫 link 만 status 전이
  유발 (이후 link 는 status 그대로).
- **민감 도메인 주의**: capture 에 finance / health-* / relationships 도메인이면
  한 줄 고지 (Codex 노출). 사용자 "보류" 하면 다음 날로.
- **잔소리 금지**: "왜 task #5 진척 없어?" 같은 질문 X.
- **KR `current` 값을 직접 큰 폭으로 bump 하지 말 것**: task 단위로만
  (quantity 없으면 +1). 큰 점프는 사용자가 `mcs okr update` 로.

## 사용 가능한 MCP 도구

| 도구 | 용도 |
|---|---|
| `mcp_mcs_memory_list_captures` | Phase 1 오늘 캡처 |
| `mcp_mcs_notion_list_daily_tasks` | Phase 1 오늘 task |
| `mcp_mcs_okr_list_active` | Phase 1 + Phase 4 KR ↔ notion_page_id 매핑 |
| `mcp_mcs_memory_add_task_link` | Phase 4 capture frontmatter `tasks:` |
| `mcp_mcs_notion_push_capture` | Phase 4 capture row → Notion Tasks relation |
| `mcp_mcs_notion_update_daily_task_status` | Phase 4 task status 전이 |
| `mcp_mcs_okr_update_kr` | Phase 4 task 완료 시 KR current 증가 |

## 종료 조건

- 반영 요약 출력 (승인 N · 반영 N · 매칭 안 된 capture N)
- 또는 사용자 취소 → "변경 없음."

## 하지 말 것

- 사용자가 명시 안 한 task 를 마음대로 `완료` 로 만들기.
- 매칭 안 된 capture 를 KR 에 직접 link (옵션 A — capture.KRs 관계 없음).
- 같은 capture↔task 쌍 재처리 (idempotency).
- 같은 KR 에 한 sync 세션에서 +3 이상 점프 (의심스러우면 나눠 묻기).
