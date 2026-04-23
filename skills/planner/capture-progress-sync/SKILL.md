---
name: capture-progress-sync
description: |
  Walks through a day's captures and proposes KR progress updates by
  cross-referencing them with active Objectives. Intended for evening
  retro cadence but can be invoked ad-hoc for any date. Slash trigger:
  `/capture-progress-sync [YYYY-MM-DD]`.
metadata:
  hermes:
    tags: [planner, okr, progress]
    requires_tools:
      - mcp_mcs_memory_list_captures
      - mcp_mcs_memory_add_okr_link
      - mcp_mcs_okr_list_active
      - mcp_mcs_okr_update_kr
---

# 캡처 진척 동기화

하루치 캡처를 돌아보고 **활성 OKR의 KR 진척에 연결**하는 스킬. 사용자가
`mcs capture --kr` 로 매번 수동 링크하지 않아도, 이 스킬이 저녁에 일괄
제안해 승인받아 반영한다.

## 당신의 역할

- **제안만 한다.** 최종 결정은 사용자.
- **짧게.** 후보 캡처·KR 쌍을 한 화면에 정리. 장황한 설명 금지.
- **이미 링크된 건 건드리지 않는다.** 중복 검증 (capture.okrs 에
  해당 kr_id 이미 있으면 스킵).

## 대화 흐름

### Phase 1 — 범위 결정

1. opener 에 날짜가 있으면 그 날짜 사용. 없으면 **오늘 KST 날짜**
   (YYYY-MM-DD 포맷).
2. `mcp_mcs_memory_list_captures(date=<that>)` 호출 → 캡처 목록.
3. 캡처 0개 → "오늘 캡처 없어. 끝." 종료.

### Phase 2 — 활성 KR 로드

1. `mcp_mcs_okr_list_active()` 호출 → active Objective 와 그 안의 KR 들.
2. KR 0개 → "지금 활성 KR 없어 — 동기화할 대상 없음." 종료.
3. 플랫 KR 리스트 만들기: id, text, parent, current/target.

### Phase 3 — 매칭 제안 (LLM 판단)

각 캡처에 대해, 문맥 (text + domain + entities + excerpt) 을 KR 리스트와
비교해 **0~N 개 후보**를 제안. 판단 기준:

- **caption 이 KR 의 실행 증거인가?** (목적어·수치·시점 일치)
- **domain 일치** (career 캡처는 career Objective 의 KR 위주)
- **entities 겹침** (같은 사람·회사 언급)

제안 형식:
```
capture [c-1] "오늘 mock interview 2회 완료" (career)
  → 2026-Q2-mle-offer.kr-2 (+2)    <근거 한 줄>
  → 2026-Q2-mle-offer.kr-3 (+0)    <참조, 증분 없음>

capture [c-2] "..."
  → (매칭 없음)
```

근거는 한 줄, 과장 금지. increment 가 0 이면 "참조만 · 진척 증분 없음".

**매칭 0개인 캡처**는 "(매칭 없음)" 명시. 사용자가 놓친 링크가 없다는
신호이기도 함.

### Phase 4 — 일괄 승인

전체 제안을 보여준 뒤 한 번에 물음:

```
승인할 쌍 번호 (여러 개면 쉼표, 전체 y, 취소 n):
```

- `y` / `yes` → 모든 제안 승인
- `n` / `no` → 취소, 아무 것도 반영 안 함
- `1,3,5` 같은 목록 → 해당 번호만
- `skip capture c-2` 같은 명령 → 해당 캡처의 모든 제안 제외

### Phase 5 — 반영

승인된 쌍 각각에 대해:

1. increment > 0 이면 `mcp_mcs_okr_update_kr(kr_id, fields={"current": <new>})`
   호출. new_current = 현재 current + increment.
   (update_kr 의 auto-transition 로직이 target 도달 시 status 자동 조정)
2. 무조건 `mcp_mcs_memory_add_okr_link(capture_id, [kr_id])` 호출해서
   capture 의 okrs frontmatter 업데이트. increment 0 인 "참조만" 도 링크는 기록.

실패한 호출이 있으면 개별 한 줄씩 보고. 전체 반영은 계속.

### Phase 6 — 요약

```
✓ 3 쌍 반영:
  capture c-1 → kr-2 (+2 → 3/5)
  capture c-1 → kr-3 (참조)
  capture c-4 → kr-1 (+1 → achieved)

1 캡처 링크 안 됨 (매칭 없었음):
  c-3 "일반 회고"

다음 체크인 언급 없이 종료.
```

## 규칙

- **같은 쌍 재처리 금지**: capture.okrs 에 이미 해당 kr_id 가 있으면
  Phase 3 제안에서 제외.
- **과장된 increment 금지**: 캡처 텍스트에 명시된 숫자 이상 제안하지 말 것.
  "mock interview 끝" → +1. "3회 완료" → +3. 불명확 → +1 보수적으로.
- **민감 도메인 주의**: 도메인이 finance / health-* / relationships 인 캡처는
  **LLM 이 Codex 를 거친다는 점** 짧게 고지. 사용자가 "보류" 하면 다음 날로.
- **잔소리 금지**: "왜 kr-X 진척이 느려?" 같은 질문 하지 말 것.

## 사용 가능한 MCP 도구

| 도구 | 용도 |
|---|---|
| `mcp_mcs_memory_list_captures` | Phase 1 날짜별 캡처 조회 |
| `mcp_mcs_okr_list_active` | Phase 2 활성 KR 맥락 로드 |
| `mcp_mcs_okr_update_kr` | Phase 5 current 증가 반영 |
| `mcp_mcs_memory_add_okr_link` | Phase 5 capture frontmatter okrs 링크 추가 |

## 종료 조건

- 반영 완료 요약 출력 (승인 쌍 수 + 반영 KR 수 + 링크 안 된 캡처 수)
- 또는 사용자가 취소한 경우: "변경 없음."
