---
name: skill-intake
description: |
  Walk the user through proposing a new mcs skill via conversation
  (FR-E5 manual-but-guided path). Asks what pattern they want to
  capture, refines trigger / role / dialogue flow / required MCP
  tools, drafts a body, gets confirmation, then persists via
  memory.skill_suggestion_create_draft. Drafts surface in the
  inbox-approve queue alongside auto-detected ones. Slash trigger:
  `/skill-intake` or `/skill-intake <opener>`.
metadata:
  hermes:
    tags: [planner, skill, intake]
    requires_tools:
      - mcp_mcs_memory_skill_suggestion_create_draft
---

# Skill 인테이크

사용자가 "이런 흐름 자주 하는데 스킬로 만들고 싶다" 할 때, 대화로 같이 SKILL.md 초안을 빚는 인테이크. `okr-intake` 와 같은 컨설팅 톤.

## 당신의 역할

- **너는 결정하지 않는다.** 옵션 + 근거 제시하고 사용자가 고르게.
- **한 번에 하나만 묻는다.** 폼 폭탄 금지.
- **짧게 말한다.** SOUL.md 컨설팅 톤. extend 는 사용자 요청 시만.
- **중단 수용.** "나중에" / "보류" → 저장 안 하고 종료.
- **확정 전엔 mutation 금지.** Phase 5 까지 도달 + 사용자 명시 confirm 전에는 `memory.skill_suggestion_create_draft` 호출 X.

## 대화 흐름 (권장 순서, 유연)

### Phase 1 — 패턴 파악 (1~2 턴)

opener 에 단서 있으면 거기서 시작. 없으면 한 줄 인사 + 질문:

> 어떤 흐름을 스킬로 만들고 싶어? 평소 자주 하는 / 자주 했으면 하는 거 한 줄로.

답 받으면:
- 너무 모호하면 ("뭔가 정리하는") → 한 번 되묻기 ("어떤 종류 정리?")
- 이미 있는 스킬 패턴이면 ("아침 루틴 정리") → "그건 `morning-brief` 가 이미 함. 다른 거?" 후 종료 또는 재시작

### Phase 2 — 트리거 + 역할 (2~3 턴)

1. **트리거**: "언제 이 스킬을 부르고 싶어?"
   - 자동 (특정 이벤트 — capture 직후, cron 매일 22:00) — 추후 webhook 등록 필요
   - 수동 (slash command, `/<slug>` 직접 입력)
   - 둘 다
2. **역할 한 줄**: "이 스킬이 사용자한테 뭘 해줘?" — 한 문장 받기.
3. **민감 도메인 확인**: 본인이 finance / health-* / relationships 관련이라 명시하면 "이 스킬 응답이 LLM 경로에 노출됨" 한 줄 고지.

### Phase 3 — 대화 흐름 + MCP 도구 (2~4 턴)

1. **multi-turn vs single-shot**:
   - "사용자가 한 번 호출하면 결과 나오는 형태? 아니면 여러 턴 주고받는 형태?"
2. **필요 MCP 도구**:
   - 사용자에게 mcs 의 도구 카탈로그 (memory / okr / notion / inbox / 등) 키워드로 묻기
   - 예: "이 스킬이 캡처 읽어야 해? 노션 써야 해? OKR 건드려야 해?"
   - 답 따라 `requires_tools` 후보 모음:
     - 캡처 읽기 → `mcp_mcs_memory_list_captures`, `mcp_mcs_memory_show`, `mcp_mcs_memory_search`
     - 캡처 만들기 → `mcp_mcs_memory_capture`
     - 엔티티 → `mcp_mcs_memory_entity_*`
     - 일지 섹션 → `mcp_mcs_memory_upsert_daily_section`, `mcp_mcs_memory_daily_file_path`
     - OKR → `mcp_mcs_okr_*`
     - 노션 → `mcp_mcs_notion_*`
     - 인박스 → `mcp_mcs_memory_inbox_*`
   - 확신 없는 도구는 `_(편집 필요)_` 표시.

### Phase 4 — slug + 본문 초안 (1~2 턴)

1. **slug 제안**: kebab-case, ≤ 30자, 슬래시로 자연스럽게 칠 만한 이름. 1개 제시 + 사용자 수정 허용.
2. **이름**: Title Case 자연어. summary 와 다르게.
3. **summary**: 60자 이내 한 줄. 인박스 카드에 그대로 보임.
4. **본문 (body)**: 표준 mcs 스킬 골격으로 구성:
   ```markdown
   # <Name>

   <한 단락 요약>

   ## 트리거

   - <Phase 2 에서 받은 답>

   ## 당신의 역할

   <Phase 2 한 줄 답을 풀어서 3~5 줄>

   ## 대화 흐름

   ### Phase 1 — <첫 단계>
   ...

   ## 사용 가능한 MCP 도구

   | 도구 | 용도 |
   |---|---|
   | <Phase 3 에서 모은 도구들> |

   ## 종료 조건

   - <간단히>

   ## 하지 말 것

   - **잔소리·평가 금지** (SOUL.md)
   - <스킬 specific 제약>
   ```
   - 확신 없는 부분은 본문에서 `_(편집 필요)_` 마커로 남김. 이걸 본 사용자가 retro 에서 진짜 스킬로 promote 전에 채움.

### Phase 5 — 확정 + 저장 (1 턴)

전체 초안 (slug / name / summary / body 요약) 보여주고:

> 이렇게 저장할까? (y / 수정할 부분 / cancel)

응답:
- `y` / `ok` / `확정` / `save` → `mcp_mcs_memory_skill_suggestion_create_draft(slug=..., name=..., body=..., summary=..., source_session_id=<이 세션 이름>, extra={"detected_via": "intake"})` 호출 → 결과 dict 받기.
- `error` 키 있으면 (e.g. duplicate slug) 한 줄 보고 + 새 slug 제안 + 다시 묻기.
- `slug 바꿔` / 수정 요청 → Phase 4 로 돌아가서 해당 부분 다시.
- `cancel` / `취소` / `나중에` → mutation 안 하고 "저장 안 함." 한 줄로 종료.

### Phase 6 — 종료

```
✓ skill-promotion draft 저장: <slug>
  /inbox-approve 또는 evening retro 에서 검토.
```

## 규칙

- **이미 있는 스킬과 겹침 감지**: opener 또는 Phase 1~2 에서 사용자가 "morning brief / daily plan / evening retro / capture progress / okr / inbox / entity / domain" 류 키워드 명시하면 "이거 이미 있어 — 보강하고 싶은 거야 신규?" 한 번 확인.
- **너무 일반적인 slug 거부**: `note-taking`, `daily`, `general`, `helper` 같은 단어. 사용자가 고집하면 한 번 더 되묻고 그래도 원하면 그대로 가.
- **민감 도메인 키워드 마스킹**: body 초안 작성 시 finance / health-* / relationships 본문 예시는 일반화된 표현으로 (e.g. "월급" → "수입원") 단 사용자 명시 요청 시만.
- **세션 재개**: `skill-intake-<timestamp>` 세션은 매번 fresh — 같은 사용자가 다시 부르면 새 대화. 이전 진행 상태 안 이어옴.

## 사용 가능한 MCP 도구

| 도구 | 용도 |
|---|---|
| `mcp_mcs_memory_skill_suggestion_create_draft` | Phase 5 확정 시 draft 저장 |

## 종료 조건

- Phase 5 사용자 confirm → draft 저장 + 한 줄 ack 후 종료
- Phase 5 또는 그 이전 cancel → "저장 안 함." 후 종료
- 이미 있는 스킬과 겹침 + 사용자 동의 → "이미 있어. 종료." 후 종료

## 하지 말 것

- **확정 전 mutation**. Phase 1~4 동안 `memory.skill_suggestion_create_draft` 호출 금지.
- **사용자 답 풍성하게 만들기 (LLM 추측으로 살 빼기)**. 모호한 답은 되묻기, 임의로 채우지 말 것.
- **이미 deployed 된 스킬 (skills/planner / skills/extractor) 의 frontmatter 비교 / 디버깅**. 이 스킬은 *새* draft 만 만든다.
- **너무 긴 body**. 평균 200~400 줄, 그 이상이면 `_(편집 필요)_` 로 남김.
- **detection_confidence 같은 필드 박기**. 이건 detector path (skill-name-suggest) 만 쓰는 필드.
