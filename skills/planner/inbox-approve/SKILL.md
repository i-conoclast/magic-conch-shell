---
name: inbox-approve
description: |
  Walk the user through every pending suggestion in the unified inbox
  (FR-G3) — entity drafts (FR-C1), future skill-promotion drafts
  (FR-E5), entity-merge suggestions (FR-C5), proactive nudges. Renders
  one numbered list, parses "1 승인 / 2 거절 / 3 내일 / all 승인 / 1-3
  승인 / cancel" directives, dispatches via memory.inbox_act. Replaces
  the older entity-approve single-source skill — same UX, broader scope.
  Slash trigger: `/inbox-approve [YYYY-MM-DD]` (date informational only).
metadata:
  hermes:
    tags: [planner, inbox]
    requires_tools:
      - mcp_mcs_memory_inbox_list
      - mcp_mcs_memory_inbox_act
      - mcp_mcs_memory_show
---

# Inbox Approve

evening retro 동안 쌓인 모든 종류의 제안을 한 화면에서 일괄 검토·승인·거절하는 스킬. 핵심:
- **소스 무관**. entity 초안, 미래의 skill 승격 제안, 병합 후보 등 모든 타입을 동일한 UI 로 처리.
- **deferred = 영속**. "내일" 한 건 다음 호출까지 큐에 남음.
- **사용자 명시 행동만**. LLM 이 "이건 분명 노이즈" 추측해서 자동 거절하지 말 것.

## 당신의 역할

- **인박스 진행자**: 번호 매겨 보여주고 사용자 응답 파싱.
- **타입별 메타 표시**: entity draft 면 첫 언급 발췌, skill 제안이면 패턴 요약, 등.
- **추가 정보 변환**: confirm 시 사용자가 한 줄로 던지는 메타 (`1 승인 role=Recruiter company=Anthropic`) 를 type 별로 알맞은 `extra` dict 로 변환.
- **짧게**. 각 항목 한 줄 + (있으면) 출처/메타 한 줄 — 그 이상 풀어쓰기 금지.

## 대화 흐름

### Phase 1 — 컨텍스트 로드

1. opener 에 날짜 있으면 표시용. 없으면 **오늘 KST**.
2. `mcp_mcs_memory_inbox_list()` — 전체 pending 항목 (newest-first).
3. 0 개 → `"no entity drafts."` 한 줄로 종료. (CLI/retro 가 이 marker 보고 깔끔히 다음 phase 로 넘어감.)

### Phase 2 — 인박스 제시 (Turn 1)

타입별 그룹 또는 단일 번호 리스트. 한 번에 너무 많으면 (≥ 8 건) 5 건씩 페이징.

```
인박스 N건:

1. [entity-draft] people/jane-smith — "Jane Smith"
   role=ML Recruiter · conf=0.95
   첫 언급: domains/career/2026-04-29-anthropic-mle-1st (Jane이 LoRA·RAG 중심…)

2. [entity-draft] companies/anthropic — "Anthropic"
   conf=0.98
   첫 언급: domains/career/2026-04-29-anthropic-mle-1st

3. [skill-promotion] daily-glance — "주중 매일 오후 'OO 진행 어디까지?' 패턴 4회 반복"
   source: entity-approve session log
   draft: .brain/skill-suggestions/daily-glance.md

처리 (예: "1 승인", "2 거절 노이즈", "3 내일", "all 승인", "1-3 승인", "cancel"):
```

타입별 표시 가이드:
- **entity-draft**: `[entity-draft] kind/slug — "name"` + meta (role/company/url/conf) + 첫 언급 발췌. 발췌는 `mcp_mcs_memory_show(query=payload.promoted_from)` 로 한 번 호출, body 첫 비어있지 않은 줄 100자 이내.
- **skill-promotion** (미래): `[skill-promotion] slug — "<요약>"` + 출처 + draft 경로.
- **그 외 type**: `summary` 그대로 사용.

### Phase 3 — 응답 파싱

지원하는 형식 (한 응답에 섞여도 OK):

| 입력 | 의미 |
|---|---|
| `1 승인` / `1 ok` / `1 yes` / `1 y` | 1번 → `inbox_act(type, id, "approve")` |
| `1 승인 role=Recruiter` | confirm + extra={"role": "Recruiter"} (type 이 entity-draft 일 때만 의미 있음) |
| `1 승인 role=Recruiter company=Anthropic` | extra 여러 필드 |
| `2 거절` / `2 no` / `2 reject` | reject |
| `2 거절 노이즈` / `2 reject duplicate` | reject + reason |
| `3 내일` / `3 later` / `3 skip` | defer (큐에 남김) |
| `all 승인` / `all yes` | 모두 confirm (extra 없음) |
| `1-3 승인` / `1,3 승인` | 범위·리스트 confirm |
| `cancel` / `취소` / `quit` | 종료, 변경 없음 |
| `more` / `다음` (페이징 중) | 다음 페이지 |

**모호하면 되묻기**: `"1 좋아"` 같은 자연어는 confirm 으로 받되 한 번 확인 (`"1번 승인 (extra 없음)? y/n"`).

### Phase 4 — 반영

각 directive 별로 `mcp_mcs_memory_inbox_act(item_type=<...>, item_id=<...>, action=<approve|reject|defer>, extra=<dict|null>, reason=<str|null>)` 호출.

`error` 키 있는 응답은 한 줄 보고 후 다음 directive 진행. 부분 실패는 무시 안 하고 요약에 명시.

### Phase 5 — 요약

처리 끝나면:

```
✓ 2 confirmed:
  - entity-draft people/jane-smith (+role=Recruiter)
  - skill-promotion daily-glance
⊘ 1 rejected:
  - entity-draft companies/anthropic (노이즈)
→ 1 deferred (인박스에 남음): entity-draft jobs/anthropic-mle

남은 인박스 1건. 계속 처리하려면 응답, 아니면 cancel.
```

남은 항목 있으면 사용자 cancel 까지 Phase 2 로 다시. 0 건이면 `"인박스 비었음."` 후 종료.

## 규칙

- **항상 명시 행동만**. 무응답은 defer 와 동치 — 자동 reject 금지.
- **active 엔티티 / 이미 확정된 skill 등 mutable-confirmed 상태 다시 안 건드림**. inbox 에 안 떠야 정상.
- **민감 도메인 발췌**: entity 출처가 finance / health-* / relationships 면 발췌 한 줄 표시는 OK 지만, 사용자 `"발췌 빼"` 하면 그 이후 항목부터 발췌 생략.
- **타입 모르는 항목**: `inbox_act` 가 `unknown inbox item type` 에러 반환 시 한 줄 보고 후 그 항목 skip.

## 사용 가능한 MCP 도구

| 도구 | 용도 |
|---|---|
| `mcp_mcs_memory_inbox_list` | Phase 1 큐 로드 |
| `mcp_mcs_memory_show` | Phase 2 entity-draft 첫 언급 발췌 (payload.promoted_from) |
| `mcp_mcs_memory_inbox_act` | Phase 4 dispatch (approve/reject/defer) |

## 종료 조건

- 인박스 0 건 → `"no entity drafts."` (또는 `"인박스 비었음."`) 후 종료.
- 사용자 cancel → 처리한 부분 요약 + `"종료."`.
- 인박스 다 처리 → 요약 + `"인박스 비었음."`.

## 하지 말 것

- **자동 reject**. 항상 사용자 명시.
- **adapter 직접 호출** (e.g. `mcp_mcs_memory_entity_confirm`). inbox_act 한 단계로만.
- **KR.current 손대기** (per `feedback_kr_current_owner`).
- **evening-retro narrative 와 중복**. 이 스킬은 인박스만, narrative 는 evening-retro 가 처리.
- **"오늘 X 건 처리해야 합니다" 식 잔소리** (SOUL.md).
