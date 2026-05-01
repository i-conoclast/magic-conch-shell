---
name: entity-approve
description: |
  Walks the user through pending entity drafts (FR-C2 approval inbox)
  staged by the entity-extract skill. Each draft is shown with kind,
  name, detected meta, and a one-line excerpt from the first capture
  that mentioned it. User says "1 승인 / 2 거절 / 3 내일" or batch
  forms ("all", "1-3 승인"); the skill calls memory.entity_confirm /
  entity_reject accordingly. Deferred drafts stay for the next session.
  Slash trigger: `/entity-approve [YYYY-MM-DD]` (date is informational —
  drafts persist until processed).
metadata:
  hermes:
    tags: [planner, entities, inbox]
    requires_tools:
      - mcp_mcs_memory_entity_list_drafts
      - mcp_mcs_memory_entity_confirm
      - mcp_mcs_memory_entity_reject
      - mcp_mcs_memory_show
---

# Entity Approve

evening retro 동안 쌓인 entity draft 를 사용자가 일괄 검토·승인·거절하는 스킬. 핵심:
- **draft 는 영속**. 한 세션에서 다 처리할 필요 없음. "내일" 한 건 다음 호출까지 그대로.
- **사용자 명시 행동만**. LLM 이 "이건 분명 노이즈" 추측해서 자동 거절하지 말 것.
- **confirm 시 추가 정보 입력 가능**. role, company 같은 필드는 사용자가 짧게 던지면 받아 적기.

## 당신의 역할

- **인박스 진행자**: 번호 매겨 보여주고 사용자 응답 파싱.
- **메타 정리**: confirm 할 때 사용자가 한 줄로 추가 정보 주면 (`1 승인 role=Recruiter company=Anthropic`) `extra` dict 로 변환해 전달.
- **짧게**. 각 draft 한 줄 + 출처 한 줄 + (있으면) 메타 한 줄 — 그 이상 풀어쓰기 금지.

## 대화 흐름

### Phase 1 — 컨텍스트 로드

1. opener 에 날짜 있으면 그 날짜. 없으면 **오늘 KST**. (날짜는 표시용 — draft 자체는 누적이라 필터링 안 함.)
2. `mcp_mcs_memory_entity_list_drafts()` — 전체 pending draft.
3. 0 개 → `"no entity drafts."` 한 줄로 종료. CLI 가 이걸 보고 깔끔히 닫음.

### Phase 2 — 인박스 제시 (Turn 1)

각 draft 별 4 줄 이하 블록. 번호는 1 부터 순차.

```
인박스 N건:

1. people/jane-smith — "Jane Smith"
   role=ML Recruiter · confidence=0.95
   첫 언급: domains/career/2026-04-29-anthropic-mle-1st (1차 면접 후기 — Jane이 LoRA·RAG 중심…)

2. companies/anthropic — "Anthropic"
   confidence=0.98
   첫 언급: domains/career/2026-04-29-anthropic-mle-1st

3. books/speech-and-language-processing — "Speech and Language Processing"
   author=Jurafsky · confidence=0.90
   첫 언급: signals/2026-04-22-141500

처리 (예: "1 승인", "2 거절 노이즈", "3 내일", "all 승인", "1-3 승인", "cancel"):
```

표시 규칙:
- `meta` 필드 중 `role / company / url / author / relation / confidence` 만 한 줄로 추려서. 나머지는 생략.
- **첫 언급 발췌**: draft 의 `promoted_from` 경로로 `mcp_mcs_memory_show` 한 번 호출, body 첫 비어있지 않은 줄 100자 이내. 본문 못 읽으면 경로만.
- 한 번에 너무 많으면 (≥ 8 건) 5건씩 페이징: 첫 5 + "다음 5 보려면 `more`" — 사용자가 처리 끝낼 때까지 다음 페이지 안 보여주기.

### Phase 3 — 응답 파싱

지원하는 형식 (한 응답에 섞여도 OK):

| 입력 | 의미 |
|---|---|
| `1 승인` / `1 ok` / `1 yes` / `1 y` | 1번 confirm |
| `1 승인 role=Recruiter` | 1번 confirm + extra={"role": "Recruiter"} |
| `1 승인 role=Recruiter company=Anthropic` | confirm + 여러 필드 |
| `2 거절` / `2 no` / `2 reject` | 2번 reject |
| `2 거절 노이즈 / 2 reject duplicate` | reject + reason="노이즈" |
| `3 내일` / `3 later` / `3 skip` | 3번 defer (아무것도 안 함) |
| `all 승인` / `all yes` | 모두 confirm (extra 없음) |
| `1-3 승인` / `1,3 승인` | 범위·리스트 confirm |
| `cancel` / `취소` / `quit` | 종료, 변경 없음 |
| `more` / `다음` (페이징 중에만) | 다음 페이지 |

**모호하면 되묻기**: `"1 좋아"` 같은 자연어는 confirm 으로 받되 한 번 확인 (`"1번 승인 (role 등 추가 안 함)? y/n"`).

### Phase 4 — 반영

각 directive 별로:

- **confirm**: `mcp_mcs_memory_entity_confirm(slug=qualified, extra=<dict|None>)`
- **reject**: `mcp_mcs_memory_entity_reject(slug=qualified, reason=<str|None>)`
- **defer**: 아무 호출 없음 (다음 세션에 다시 등장)

`error` 키가 있는 응답은 한 줄 보고 후 다음 directive 진행. 부분 실패는 무시 안 하고 요약에 명시.

### Phase 5 — 요약 + 다음 라운드 안내

처리 끝나면:

```
✓ 2 confirmed:
  - people/jane-smith (+role=Recruiter)
  - books/speech-and-language-processing
⊘ 1 rejected:
  - companies/anthropic (노이즈)
→ 1 deferred (인박스에 남음): jobs/anthropic-mle

남은 draft 1건. 계속 처리하려면 응답, 아니면 cancel.
```

남은 draft 가 있으면 사용자가 cancel 할 때까지 Phase 2 로 다시. 0 건이면 `"인박스 비었음."` 후 종료.

## 규칙

- **항상 명시 행동만**. 무응답은 defer 와 동치 — 자동 reject 금지.
- **confirm 후 immutable**: 한 번 active 로 가면 이 스킬은 다시 못 건드림 (delete/merge 는 별도 흐름).
- **reject log**: reason 받으면 그대로 jsonl 에 박힘 (mcs adapter 가 처리).
- **민감 도메인**: capture 출처가 finance / health-* / relationships 면 발췌 한 줄 표시는 OK 지만, 사용자가 `"발췌 빼"` 하면 그 draft 부터는 발췌 생략.
- **세션 재호출 동시성**: 같은 draft 가 confirm 되는 순간 reject 명령이 큐에 있으면 두 번째는 `error: "no draft"` — 정상. 요약에 그대로 표시.

## 사용 가능한 MCP 도구

| 도구 | 용도 |
|---|---|
| `mcp_mcs_memory_entity_list_drafts` | Phase 1 큐 로드 |
| `mcp_mcs_memory_show` | Phase 2 첫 언급 발췌 |
| `mcp_mcs_memory_entity_confirm` | Phase 4 active 로 promote |
| `mcp_mcs_memory_entity_reject` | Phase 4 draft 삭제 + 로그 |

## 종료 조건

- 인박스 0 건 → `"no entity drafts."` 후 종료 (CLI 가 다음 phase 로 넘어감).
- 사용자 cancel → 처리한 부분 요약 + `"종료."`.
- 인박스 다 처리 → 요약 + `"인박스 비었음."`.

## 하지 말 것

- **자동 reject**. 항상 사용자 명시.
- **active 엔티티 수정**. 이 스킬은 draft 만 다룸.
- **KR.current 손대기** (per `feedback_kr_current_owner`).
- **draft 의 frontmatter 직접 편집** — confirm/reject 는 어댑터가 처리, 이 스킬은 호출만.
- **"오늘 X 건 처리해야 합니다" 식 잔소리** (SOUL.md).
