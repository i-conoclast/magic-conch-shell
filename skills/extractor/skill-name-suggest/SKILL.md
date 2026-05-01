---
name: skill-name-suggest
description: |
  Given a cluster of similar captures detected by the FR-E5 ANN
  detector, propose a skill-promotion draft (slug, name, summary,
  body skeleton). Single-shot — the caller invokes this once per
  candidate cluster from `mcs skill scan` and persists the JSON
  response via skill_suggestion.create_draft.
metadata:
  hermes:
    tags: [extractor, meta, skill-promotion]
    requires_tools: []
---

# Skill Name Suggest

mcs detector 가 캡처들 사이에서 **반복 패턴(클러스터)** 을 발견했을 때, 이 패턴을 어떤 이름의 스킬로 만들면 좋을지 한 번에 제안하는 스킬. 핵심:

- **수동 검토 게이트가 그 다음에 있다**. 이 스킬이 정답을 내는 게 아니라, **인박스에 올릴 후보 한 줄**을 만드는 거. 사용자가 evening retro 에서 승인·거절·편집함.
- **추측 OK 단 보수적으로**. 클러스터가 약하면 `slug: null` 로 응답 가능 (이 클러스터는 스킬 가치 없음 신호).

## 입력 형식

호출자(`mcs skill scan` → `skill_labeler`) 가 다음 형태로 opener 를 만든다:

```
cluster_seed: <seed_id>
member_count: <N>
time_spread_days: <X.X>
domains: [career, ml, ...]   # 비어있을 수 있음
sample_excerpts:
  1. <첫 200자>
  2. <첫 200자>
  ...
  (최대 5개)
```

## 출력 형식

**반드시 단일 JSON 객체** 를 출력. 그 외 설명·인사말 금지.

```json
{
  "slug": "kebab-case-slug",
  "name": "Display Name",
  "summary": "한 줄 요약 (60자 이내)",
  "body": "## 트리거\n\n...\n\n## 당신의 역할\n\n...\n\n## 대화 흐름\n\n...\n\n## 사용 가능한 MCP 도구\n"
}
```

또는 클러스터가 스킬 가치 없다고 판단 시:

```json
{
  "slug": null,
  "reason": "samples are heterogeneous — no clear repeating workflow"
}
```

## 규칙

- **slug 형식**: 소문자 + 하이픈만. 한글·공백·특수문자 X. 길이 ≤ 30자.
- **slug 의미**: 사용자가 슬래시 트리거로 자연스럽게 칠 만한 이름. (예: `lunch-log`, `code-review-checklist`, `weekly-finance-roundup`)
- **name**: Title Case 자연어. summary 와 중복되면 안 됨.
- **summary**: 패턴이 무엇인지 60자 이내. 잔소리·평가 X.
- **body**: 표준 mcs 스킬 골격 — `## 트리거 / ## 당신의 역할 / ## 대화 흐름 (Phase 1~) / ## 사용 가능한 MCP 도구`. 각 섹션에 클러스터에서 추정한 구체 내용 넣되, **확신 없는 부분은 `_(편집 필요)_` 로 표시**.
- **null 응답 기준**: samples 끼리 주제가 다르거나 (e.g. 1개는 면접, 1개는 운동, 1개는 책), 모두 같은 단발 이벤트의 다른 면면 (e.g. 면접 1회의 4가지 단계) 일 때.

## 하지 말 것

- **JSON 외 텍스트**. preamble, markdown, ``` 펜스 모두 금지. 호출자가 `json.loads` 함.
- **이미 존재하는 스킬과 중복되는 slug**. samples 가 명백히 morning-brief / daily-plan / capture-progress-sync / okr-intake / okr-update / evening-retro / inbox-approve / entity-extract / domain-classify 패턴이면 → null + reason 으로 응답.
- **너무 일반적인 slug** (`note-taking`, `daily`, `general`). 구체적인 워크플로 이름이어야 함.
- **민감 도메인 노출**: samples 에 finance / health-* / relationships 가 보이면 slug 에 그 도메인을 박지 말고 (예: `monthly-money` 보다 `monthly-summary`) — 사용자가 직접 편집해서 박을 일.

## 참고

- 입력 클러스터는 ANN cosine similarity 기반이라 같은 단어 반복 ≠ 같은 워크플로일 수 있음. 의미 차이 의심 시 null.
- summary 한 줄은 그대로 인박스 카드에 표시됨 — 사용자가 슬쩍 보고 판단하는 게 핵심.
