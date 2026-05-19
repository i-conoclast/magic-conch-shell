---
name: capture-intake
description: |
  Capture a one-line memo into brain/signals/ via the mcs MCP adapter
  (`mcp_mcs_memory_capture`) — same SSoT path as `mcs capture` and
  signals/ markdown drops. Single-shot: takes the opener text, asks at
  most one short follow-up for optional KR back-links, then writes.
  Domain classification and entity extraction are NOT handled here —
  the mcs daemon's webhook pipeline fires `domain-classify` and
  `entity-extract` automatically right after capture. Slash trigger:
  `/capture-intake <text>` or `/capture-intake` (then prompts for text).
metadata:
  hermes:
    tags: [planner, capture]
    requires_tools:
      - mcp_mcs_memory_capture
      - mcp_mcs_okr_list_active
---

# Capture Intake

`mcs capture` / signals 드롭과 동등한 세 번째 진입 경로. 대화로 한 줄 메모를
받아 `mcp_mcs_memory_capture` 한 번에 저장하는 얇은 planner 래퍼다.

핵심:
- **너는 분류기가 아님.** domain / entity 는 capture 후 daemon webhook 이
  `domain-classify` + `entity-extract` 를 자동 발동시켜 채운다. 이 스킬은
  본문 + (옵션) KR back-link 만 받고 손 뗀다.
- **single-shot.** opener 충분하면 추가 질문 없이 바로 저장. 모자라면 한 번
  되묻고 끝.
- **너는 결정하지 않는다.** KR 후보 보여주고 사용자가 고른다.
- **짧게.** 결과는 한두 줄 (`✓ signal · <id> · <rel_path>`).

## 트리거

- `/capture-intake` — opener 없음 → "한 줄로 적어줘" 한 번 묻기.
- `/capture-intake <text>` — opener 가 곧 본문.
- `/capture-intake <text> --kr <id>` 같은 플래그 어울려 들어오면 그대로
  파싱해서 후속 질문 생략.

## 당신의 역할

- **본문 정리**: opener 가 여러 문장이면 한 줄로 줄여줄지 묻기 (단, 사용자가
  명시적으로 길게 적었으면 그대로 두기).
- **KR 매칭 제안 (optional)**: 본문에 OKR 도메인 단서 (회사명·면접·운동·돈
  등) 보이면 `mcp_mcs_okr_list_active(domain=<추정>)` 한 번 호출해서 후보
  KR 1~3개 제안. 단서 없거나 사용자가 "그냥 capture" 하면 KR 단계 건너뛰기.
- **저장**: 사용자가 확정하면 `mcp_mcs_memory_capture` 호출. 그 외 mutation
  금지.

## 대화 흐름

### Phase 1 — opener 파싱

1. opener 텍스트 추출.
2. opener 비어있으면 한 줄: `한 줄로 적어줘 (취소: n).` → 사용자 응답 받기.
3. 사용자 응답이 `n` / `취소` / 빈 줄 → "취소함." 종료.
4. opener 에 `-d <domain>` / `-e <entity>` / `-k <kr-id>` 형식 플래그가
   있으면 분리 (`mcs capture` CLI 와 호환). 분리 후 본문이 비면 다시 텍스트
   재요청.

### Phase 2 — KR back-link (optional, 0~1 턴)

다음 중 하나면 KR 단계 **건너뛰기**:
- opener 에 `-k` 또는 `--kr` 가 이미 들어있음
- 본문이 너무 짧음 (10자 미만) 또는 도메인 단서 없음
- 사용자가 opener 에 "그냥 적어줘" / "no kr" 류 명시

그 외에는 한 번만 묻기:

1. 본문 키워드로 도메인 추정 (`career` / `ml` / `health-physical` 등 7개 중).
   확신 없으면 추정 건너뛰고 KR 단계도 skip.
2. `mcp_mcs_okr_list_active(quarter=<현재 분기>, domain=<추정>)` 호출.
3. KR 0개 → KR 단계 skip (사용자 귀찮게 안 하기).
4. KR ≥1 개 → 후보 1~3개 한 줄씩 보여주기:
   ```
   관련 KR 후보 (skip 하려면 그냥 엔터):
     1. 2026-Q2-career-mle-role.kr-2  "Anthropic 2차 면접 통과"
     2. 2026-Q2-career-mle-role.kr-1  "MLE 포지션 3곳 1차 통과"
   ```
5. 사용자 응답:
   - 엔터 / `skip` / `n` → KR 없이 진행
   - `1` / `1,2` / `1번` → 해당 번호의 kr_id 들을 okrs 리스트에 담기
   - `<kr-id>` 직접 입력 → 그대로 사용

**현재 분기 계산**: 오늘 KST 기준 1-3=Q1, 4-6=Q2, 7-9=Q3, 10-12=Q4.

### Phase 3 — 저장

`mcp_mcs_memory_capture` 한 번 호출:

```
mcp_mcs_memory_capture(
  text=<본문>,
  domain=<-d 로 명시된 값 또는 None>,  # None 이면 webhook 이 채움
  entities=[<-e 들>],                   # 없으면 빈 리스트
  okrs=[<Phase 2 에서 고른 kr_id 들>],
  source="typed",
  index=True,
  push_notion=True,
)
```

응답 키: `path`, `rel_path`, `id`, `type`, `domain`, `indexed`,
`notion_pushed`, `notion_page_id`.

`error` 키 있으면 한 줄로 보고 후 종료.

### Phase 4 — 결과 출력

성공 시 1~2줄:

```
✓ signal · <id>
  brain/signals/<...>.md
  (domain/entity 는 잠시 후 자동 분류됨)
```

도메인이 명시 입력으로 박힌 경우:
```
✓ note · <id> · domain=career
  brain/domains/career/<...>.md
```

`indexed=False` 면 한 줄 경고 추가 (`⚠ indexing skipped`).
`notion_pushed=False` 면 한 줄 (`⚠ notion push skipped`) — 치명적 아님.

## 규칙

- **언어 일치**: 사용자가 한국어로 적었으면 본문 그대로 저장. 자동 번역 X.
- **본문 가공 최소화**: opener 가 그대로 메모로 쓸 만하면 손대지 말 것.
  여러 문장이거나 잡담 섞였을 때만 한 줄 요약 제안 (사용자 동의 시).
- **domain / entity 직접 호출 금지**: `mcp_mcs_memory_set_domain`,
  `mcp_mcs_memory_show` 등은 이 스킬에서 호출하지 않는다. 그건 webhook
  으로 발동되는 [[domain-classify]] / [[entity-extract]] 의 책임.
- **KR `current` bump 금지**: 이 스킬은 capture 만 한다. KR 진척 반영은
  `mcs capture --increment` CLI 또는 [[capture-progress-sync]] 에서.
- **민감 도메인 주의**: 본문에 `finance / health-* / relationships`
  단서가 강하면 한 줄 고지 (`이 내용은 Codex 에 갈 수 있어`). 사용자가
  "취소" 하면 capture 호출 안 함.
- **중복 방지**: 같은 옵저버에서 동일 텍스트가 5초 안에 두 번 들어오면
  한 번만 저장 — daemon 이 이미 idempotency 처리하지만 너도 한 번 묻기.

## 사용 가능한 MCP 도구

| 도구 | 용도 |
|---|---|
| `mcp_mcs_memory_capture` | Phase 3 본문 저장 |
| `mcp_mcs_okr_list_active` | Phase 2 KR 후보 조회 (optional) |

## 종료 조건

- capture 저장 + 한두 줄 결과 출력
- 또는 사용자 취소 → "취소함." (mutation 없음)
- `memory.capture` 에러 응답 → 한 줄 에러 후 종료

## 하지 말 것

- domain / entity 직접 추정해서 set_domain 호출 (webhook 의 책임).
- 본문을 영어로 번역하거나 윤색.
- KR 후보 강요 — 사용자가 skip 하면 그냥 capture.
- 같은 본문 재호출 (`mcs capture` 와 이 스킬은 같은 SSoT — 중복 X).
- 결과에 본문 다시 인용해서 길게 늘어뜨리기. SOUL.md 의 terse 원칙.

## 자동 트리거 (없음 — 수동 슬래시 전용)

이 스킬은 **사용자가 직접 부를 때만** 동작한다. capture-progress-sync 나
inbox-approve 처럼 cadence 가 정해진 게 아니다. webhook 도 안 받는다.
daemon → 이 스킬 호출 경로는 없음.
