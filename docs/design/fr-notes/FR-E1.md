# FR-E1: 워크플로 = 마크다운 1파일

**카테고리**: E. Sessions
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

학습·상담 세션(영어 회화·ML 공부·모의 면접 등) = **agent 마크다운 1파일 + state 폴더**. 사용자가 읽고 쓰고 수정 가능.

**구조 확정**: 3-tier 구조에서 "workflow" = **agent** (01-extension-model.md 반영).

---

## 2. 관련 컴포넌트

- **Agents**: `agents/{name}.md` 표준 (01-extension-model Section 3)
- **State**: `brain/session-state/{name}/state.yaml` + `logs/`
- **Commands**: `commands/{name}.md` (명시 호출)
- **Tools**: `memory`, `llm`, `hermes` (subagent 호출)

---

## 3. 파일 구조 복기

```
agents/tutor-english.md       ← agent 정의 (persona + flow + tools)
brain/session-state/tutor-english/
├── state.yaml                ← 진도 (회차, 현재 주제, 레벨)
└── logs/
    ├── 2026-04-19.md         ← 회차별 대화 요약
    └── 2026-04-15.md
```

---

## 4. Agent .md 예시

`agents/tutor-english.md`:
```markdown
---
name: tutor-english
description: English conversation session runner. Resumes from last session progress automatically.
tools: [memory, llm, hermes]
model: ollama-local
isolation: fork
state_path: brain/session-state/tutor-english/
max_turns: 50
memory: persistent
---

# English Tutor

## Persona
You are an English conversation partner for the user.
Adapt to user's level. Be patient and encouraging.
Correct grammar gently, explain only when needed.

## Session structure
1. Read state.yaml → last session date, last topic, level, upcoming topics
2. Brief recap of last session ("Last time we covered ___")
3. Ask what user wants today — free conversation / specific topic / review
4. Flow conversation naturally, target ~20~30 minutes
5. Save progress + today's log to state_path

## Rules
- No Korean translation unless explicitly asked
- Adjust difficulty based on response quality
- Keep it encouraging, never demeaning
- If user wants to stop, save and exit cleanly

## References
Session state schema: see [state-schema.md](state-schema.md)
```

---

## 5. State 파일 예시

`brain/session-state/tutor-english/state.yaml`:
```yaml
agent: tutor-english
session_count: 8
last_session_at: "2026-04-15T19:30:00+09:00"
last_session_duration_minutes: 28
current_level: intermediate
current_topic: Past perfect tense
upcoming_topics:
  - Conditional sentences
  - Reported speech
completed_topics:
  - Past simple / continuous
  - Present perfect
vocabulary_focus:
  - commitment
  - trade-off
  - throughput
notes: "User prefers short, rapid exchanges. Struggles with articles."
```

---

## 6. Session Log 예시

`brain/session-state/tutor-english/logs/2026-04-19.md`:
```markdown
---
agent: tutor-english
session_number: 9
date: 2026-04-19
duration_minutes: 25
topic: Past perfect tense
vocabulary_new: [had been, by the time]
---

## Recap
Started with recap of past simple vs continuous.

## Flow
- Practice sentences with "had + past participle"
- Introduced "by the time ___ had ___"
- Conversation about yesterday's events

## Observations
- Grammar: mostly correct, occasional article errors
- Pace: good
- Engagement: high

## Next
- Conditional sentences (1st and 2nd)
```

---

## 7. 구현 노트

세션 실행은 Hermes가 처리:
- agent.md 로드 → persona + flow
- state_path/state.yaml 읽어 컨텍스트 주입
- 세션 진행 (LLM 호출, isolation=fork로 격리)
- 세션 종료 시 state.yaml·logs 갱신 (Hermes skill "save-session-state")

```python
# tools/sessions.py (지원 함수)
async def session_start(agent_name: str) -> dict:
    agent_path = f"agents/{agent_name}.md"
    state_path = f"brain/session-state/{agent_name}/state.yaml"
    state = yaml.safe_load(await file.read(state_path)) if await file.exists(state_path) else {}
    return {"agent_path": agent_path, "state": state}

async def session_end(agent_name: str, new_state: dict, log_body: str) -> None:
    # state 갱신
    state_path = f"brain/session-state/{agent_name}/state.yaml"
    new_state["session_count"] = new_state.get("session_count", 0) + 1
    new_state["last_session_at"] = now_kst().isoformat()
    await file.write(state_path, yaml.dump(new_state))

    # 로그 저장
    log_path = f"brain/session-state/{agent_name}/logs/{date.today().isoformat()}.md"
    await file.write(log_path, log_body)
```

---

## 8. 테스트 포인트

- [ ] agents/tutor-english.md 로드 성공
- [ ] state.yaml 없을 때 (첫 세션) 기본값으로 시작
- [ ] 세션 종료 시 state·log 저장 확인
- [ ] isolation=fork가 메인 대화 컨텍스트와 분리
- [ ] 프론트매터 필드 오류 시 해당 agent만 로드 실패, 다른 agent 정상

---

## 9. 리스크·완화

| 리스크 | 완화 |
|---|---|
| state.yaml 손상 → 세션 리셋 | `.bak` 파일 유지 |
| Hermes subagent 기능 버전별 변경 | 변경 탐지 + adapter 레이어 |
| 세션 중 Hermes 종료 | 진도 자동 flush (30초마다) |

---

## 10. 관련 FR

- **FR-E2** 명시·자동 호출
- **FR-E3** 진도 승계
- **FR-E4** DIY 추가
- **FR-E5** 자동 승격

---

## 11. 구현 단계

- **Week 3 Day 4**: agents/tutor-english.md 샘플 + state 스키마
- **Week 3 Day 5**: Hermes subagent 실행 테스트
- **Week 3 Day 6**: 세션 로그 자동 저장
