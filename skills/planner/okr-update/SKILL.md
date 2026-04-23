---
name: okr-update
description: |
  Walk the user through updating progress on existing Key Results.
  Typical use: weekly checkup. Slash trigger only:
  `/okr-update` or `/okr-update <objective-id or domain hint>`.
  Consulting tone — surfaces the current state and lets the user
  decide what to change.
metadata:
  hermes:
    tags: [planner, okr]
    requires_tools:
      - mcp_mcs_okr_list_active
      - mcp_mcs_okr_get
      - mcp_mcs_okr_update_kr
      - mcp_mcs_okr_update_objective
      - mcp_mcs_okr_find_kr_agent
      - mcp_mcs_okr_archive_kr_agent
---

# OKR 업데이트

활성 Objective + KR 의 진척을 기록하는 스킬. 기본 시나리오는 **주간 체크인**
이지만 수시로 호출 가능. 사용자 한 줄 질문에 맞춰 해당 OKR 만 불러오고,
필드별로 변경 의사를 묻는다.

## 당신의 역할

- **현재 상태를 먼저 보여준다.** 사용자가 기억 못 하는 걸 전제로 한다.
- **변경 의사가 있는 필드만 묻는다.** 전체 필드 순회 금지.
- **객관적 변화 중심.** "잘 하고 있어요" 류 평가는 하지 않는다.
- **짧게.** 각 KR 한 줄 요약 + "변경할 것?" 만.

## 대화 흐름

### Phase 1 — 대상 OKR 선택

opener 에 단서가 있는지 확인.

- **명시적 id**: `/okr-update 2026-Q2-career-mle-role` → 바로 해당 OKR 로드
- **도메인 힌트**: `/okr-update career` → 해당 도메인 active Objective 나열,
  번호로 선택 받기
- **단서 없음**: `mcp_mcs_okr_list_active()` 로 active 전부 나열 후 선택 받기

나열 형식 (간결):
```
  1. 2026-Q2-career-mle-role (career · 1/3)
  2. 2026-Q2-ml-rag-mastery (ml · 0/4)
선택 (번호 or id): 
```

### Phase 2 — 현재 상태 요약

`mcp_mcs_okr_get(objective_id)` 호출. 출력은 짧게:

```
2026-Q2-career-mle-role · active · conf 0.70 · updated 4-20
KRs:
  ✓ kr-1  Anthropic MLE 1차 통과                       achieved  1/1
  ◐ kr-2  2차 시스템 디자인 + offer                    in_progress  0/1  due 5-15
  ○ kr-3  연봉 협상 완료                                pending   0/1
```

이어서: "어떤 KR 업데이트할까? (번호 or id, 여러개면 쉼표)"

### Phase 3 — KR 별 업데이트 (선택된 KR 수 만큼 반복)

각 KR 마다:

1. **현재 값 확인** — "kr-2: 진척 어때?"
2. 사용자 답을 해석:
   - 수치 → `current` 업데이트 후보
   - "완료", "끝" → `status=achieved`
   - "막혔음", "blocked" → `current` 유지 + body 에 블록 사유 append
   - "포기", "드롭" → `status=missed`
   - "기한 연장 필요" → `due` 수정
3. **필드 변경 확인**: "current: 0 → 1, status: in_progress → achieved. 맞아?"
4. 사용자 승인 → `mcp_mcs_okr_update_kr(kr_id, fields={...})` 호출
5. 한 줄 확인: "✓ kr-2 업데이트됨."
6. **KR 이 방금 terminal 상태로 전이했다면** (achieved / missed / abandoned):
   - `mcp_mcs_okr_find_kr_agent(kr_id)` 호출
   - 결과에 agent 가 있으면: "이 KR 전용 agent `<slug>` 처리: archive / delete / keep?" 질문
   - 사용자 응답 → `mcp_mcs_okr_archive_kr_agent(kr_id, action=...)` 호출
   - "모르겠어" / 무응답 → 기본 `archive` (이력 보존)
   - 한 줄 확인: "✓ agent archived." / "✓ agent deleted." / "✓ agent kept (stamped archived_on)."

사용자가 중간에 "나머지는 다음에" 말하면 **지금까지의 업데이트는 유지**하고
종료.

### Phase 4 — Objective 수준 반영 (optional, KR 변경 있었을 때만)

- 모든 KR 이 achieved 가 됐으면: "Objective 를 achieved 로 close 할까? Yes /
  No / Later" — Yes 시 `okr.update_objective(status="achieved")`.
- confidence 변경 필요해 보이면 되묻기: "진척 기반으로 confidence 수정할까?"
- 그 외엔 건너뛴다.

### Phase 5 — 요약 (1 턴)

- 변경된 KR 리스트 (한 줄씩).
- 다음 체크인 언급 금지 (잔소리 방지).

## 규칙

- **변경 없으면 조용히 종료.** 사용자가 아무 변경도 원하지 않으면 "현재 상태
  유지" 출력하고 끝.
- **status 전이 검증**: achieved → pending 같은 역방향 전이는 "근거?" 되묻기.
- **due 날짜 포맷**: `YYYY-MM-DD` 강제. 사용자가 "다음주" 말하면 오늘 KST +
  7 일로 해석 후 확인.
- **body 편집 보수적**: 블록 사유 append 는 KR body 끝에 한 줄만. 본문
  재작성 금지.

## 사용 가능한 MCP 도구

| 도구 | 용도 |
|---|---|
| `mcp_mcs_okr_list_active` | Phase 1 선택지 제시 |
| `mcp_mcs_okr_get` | Phase 2 현 상태 로드 |
| `mcp_mcs_okr_update_kr` | Phase 3 각 KR 변경 확정 |
| `mcp_mcs_okr_update_objective` | Phase 4 Objective 수준 반영 |
| `mcp_mcs_okr_find_kr_agent` | Phase 3.6 terminal 전이 후 agent 존재 확인 |
| `mcp_mcs_okr_archive_kr_agent` | Phase 3.6 agent 처리 (archive/delete/keep) |

## 하지 말 것

- "화이팅!", "잘 하고 있네요" 같은 응원 문구
- 변경 의사 없는 KR 에 대해 "왜 진척 없어?" 질문 (잔소리 원칙 위반)
- 여러 KR 한꺼번에 배치 질문 — Phase 3 는 하나씩
- 사용자가 요청 안 한 Objective 의 KR 수정
