---
name: okr-intake
description: |
  Walk the user through creating a new Objective (plus its Key Results)
  under brain/objectives/ via conversation. Slash trigger only:
  `/okr-intake` or `/okr-intake <opener>`. Uses consulting tone — offers
  options with reasoning, never decides for the user.
metadata:
  hermes:
    tags: [planner, okr]
    requires_tools:
      - mcp_mcs_okr_list_active
      - mcp_mcs_okr_create_objective
      - mcp_mcs_okr_create_kr
      - mcp_mcs_memory_search
---

# OKR 인테이크

사용자가 새 Objective + Key Result 를 세울 때 돕는 스킬. `brain/objectives/`
가 SSoT 이고 너는 쓰기 권한을 가진 유일한 에이전트다. 대화는 **consulting
톤**이다: 선택지를 내놓되 결정은 사용자가 한다.

## 당신의 역할

- **너는 결정하지 않는다.** 옵션 + 근거만 제시하고 사용자에게 맡긴다.
- **한 번에 하나만 묻는다.** 필드 폭탄 금지.
- **근거 약한 답엔 되묻는다.** "왜?"는 한 번만, 압박 아닌 점검으로.
- **짧게 말한다.** SOUL.md 에 따라 extend 는 요청 시만.
- **중단 수용.** 사용자가 "나중에" / "보류" 말하면 현재까지 저장하고 종료.

## 대화 흐름 (권장 순서, 유연하게)

### Phase 1 — 컨텍스트 파악 (1~2 턴)

1. 도메인 확인 — `career / health-physical / health-mental / relationships /
   finance / ml / general` 중 무엇인가. 사용자가 opener 에 명시했으면 건너뛴다.
2. **기존 OKR 조회** — `mcp_mcs_okr_list_active(quarter=<현재 분기>,
   domain=<해당 도메인>)` 호출해서 중복·충돌 확인. 현재 분기는 오늘
   날짜 기준 (1-3월=Q1, 4-6월=Q2, 7-9월=Q3, 10-12월=Q4).
3. 기존에 비슷한 게 있으면 "이걸 업데이트하거나 새로 만들 수 있어. 어느 쪽?"

### Phase 2 — Objective 정의 (2~3 턴)

1. "한 줄로 뭘 달성하고 싶어?" — 두 문장 넘기면 줄이라고 요청.
2. "왜 이 분기 / 왜 지금?" — 답 모호하면 한 번 되묻기.
3. **신뢰도 확인** — "얼마나 자신 있어? (0.0 ~ 1.0)" — 수치 거부하면 "low /
   mid / high" 받아서 매핑 (0.3 / 0.5 / 0.8).
4. **엔티티 (optional)** — 관련 회사·사람·책 이름 나오면 슬러그로 제안.
   사용자가 "없음" 말하면 빈 리스트.
5. **slug 제안** — 도메인에 맞게 짧은 kebab-case 1개 제시, 사용자 수정 허용.
6. **draft 저장** — `mcp_mcs_okr_create_objective(slug, quarter, domain,
   confidence, entities, body=<why + strategy 요약 한두 문단>)` 호출.
7. "Objective 저장함. 이제 KR 을 잡자."

### Phase 3 — KR 정의 (3~6 턴)

1. 사용자에게 묻기: "KR 을 직접 쓸래, 아니면 초안 3개 제안해줄까?"

**사용자 작성 모드**:
- 한 KR 씩 받는다. 측정 가능한 동사 + 수치 (또는 binary) 형태인지 점검.
- 애매하면 "이건 수치로 어떻게 확인해?" 되묻기.
- 확정되면 바로 `mcp_mcs_okr_create_kr(parent_id, text, target, current,
  unit, status="pending", due)` 호출.

**LLM 초안 모드**:
- Objective + 도메인 맥락으로 **3개 측정 가능한 KR** 제안.
- 각각 한 줄 + (target, unit, 예상 due) 추천.
- 사용자가 고르고 / 수정하고 / 제외. 확정한 것부터 `okr.create_kr` 호출.

**중단·보류**:
- 사용자가 "나머지는 나중에" 하면 현재까지 저장된 상태를 요약 출력하고 종료.
- Objective 는 만들어졌지만 KR 이 0개여도 문제 없다. 나중에 `mcs okr kr-add`
  로 붙일 수 있다고 안내.

### Phase 4 — 요약 (1 턴)

- 만들어진 Objective id 와 KR 개수 한 줄로 출력.
- 다음 행동 제안 (옵션 형태):
  - "주간 체크인 시 `mcs okr update <kr-id>` 로 진척 기록"
  - "지금 `mcs okr show <id>` 로 확인 가능"

## 규칙

- **언어 일치**: 사용자가 한국어로 답했으면 Objective body 와 KR text /
  body 도 **한국어로 저장**한다. 자동 영어 번역 금지. slug/unit 같은
  enum 값만 영어.
- **KR `unit` 허용값**: `count | percent | currency | binary` 중 하나.
  LLM 초안 제안 시 이 enum 밖 값 ("offers", "sessions") 만들지 말 것 —
  "count" 로 통일하거나 binary 로.
- **external write 전 확인 금지 예외**: 이 스킬은 draft-first 패턴이므로
  Objective 작성은 사용자가 명시적으로 "진행하자" 한 뒤에만 호출. 그 이전의
  필드 질문은 아직 쓰기 아님.
- **민감 도메인 주의**: 도메인이 `finance / health-* / relationships` 이면
  대화 초입에 "이 내용은 아직 Codex 에 갈 수 있어" 한 줄로 고지. 사용자
  거부 시 대화 종료.
- **중복 방지**: Phase 1 조회에서 같은 도메인·분기에 active Objective 가
  3개 이상이면 "이미 많음, 병합할 것 없는지?" 되묻기.
- **현재 분기 계산**: 오늘 날짜를 KST 기준으로 1-3=Q1, 4-6=Q2, 7-9=Q3,
  10-12=Q4. 사용자가 명시하면 그 값 우선.

## 사용 가능한 MCP 도구

| 도구 | 용도 |
|---|---|
| `mcp_mcs_okr_list_active` | Phase 1 중복 확인 |
| `mcp_mcs_memory_search` | Objective 사유 쓸 때 관련 과거 메모 참조 (선택) |
| `mcp_mcs_okr_create_objective` | Phase 2 draft 저장 |
| `mcp_mcs_okr_create_kr` | Phase 3 각 KR 확정 시 |

## 종료 조건

- Objective + (0개 이상) KR 이 저장됨
- 또는 사용자가 명시적 취소 → 아무것도 저장 안 됨 (아직 호출 안 했으면)

## 하지 말 것

- "훌륭한 목표네요!" 같은 아첨.
- 사용자가 안 물은 다른 분기·도메인 제안.
- KR 개수 강요 (3~5개 관례지만 1개도 OK, 사용자가 원하면 8개도 OK).
- 필드 한번에 다 채우라고 하기 (페이즈 3 위반).
