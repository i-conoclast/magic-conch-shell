# FR-E3: 세션 진도 저장·승계

**카테고리**: E. Sessions
**우선순위**: 높음 (MVP 필수 — Step 7 성공 신호 #2)

---

## 1. Overview

같은 workflow 반복 시 **지난번 상태가 자동 이어짐**. 사용자가 "지난번 어디까지 했지?"를 따로 말하지 않아도 됨.

---

## 2. 관련 컴포넌트

- **State**: `brain/session-state/{agent}/state.yaml`
- **Logs**: `brain/session-state/{agent}/logs/YYYY-MM-DD.md`
- **Tools**: `tools/sessions.py` (세션 라이프사이클)
- **Agent**: FR-E1에서 state_path 필드 사용

---

## 3. 라이프사이클

### 세션 시작
```
agent invoked
   → sessions.session_start(agent_name)
     - state.yaml 읽기
     - 없으면 {} 반환
   → agent persona + state 컨텍스트에 주입
   → 사용자 인사
```

### 세션 진행
- 대화 중 진도 업데이트 항목 추적 (current_topic, vocabulary 등)
- 30초마다 임시 flush (비정상 종료 대비)

### 세션 종료
```
agent gracefully ends (user "그만" or max_turns 도달)
   → sessions.session_end(agent_name, new_state, log_body)
     - state.yaml 갱신 (session_count++, last_session_at, current_topic 등)
     - logs/YYYY-MM-DD.md 작성
   → 사용자에게 요약 알림 ("session saved")
```

---

## 4. State 스키마 (agent별 확장)

공통:
```yaml
agent: {slug}
session_count: int
last_session_at: ISO 8601 +09:00
last_session_duration_minutes: int
```

tutor-english 확장:
```yaml
current_level: beginner | intermediate | advanced
current_topic: str
upcoming_topics: list[str]
completed_topics: list[str]
vocabulary_focus: list[str]
notes: str
```

tutor-ml 확장:
```yaml
current_module: str      # "Attention" | "LoRA" | "RLHF" 등
projects_active: list[str]
skills_practiced: list[str]
resources_in_progress: list[{title, url, progress}]
```

interviewer 확장:
```yaml
target_company: str
target_role: str
rounds_completed: int
weak_areas: list[str]
mock_history: list[{date, focus, outcome}]
```

각 agent가 자기 스키마 자유롭게. 공통 필드만 강제.

---

## 5. 구현 노트

### 세션 시작 시 컨텍스트 주입
agent flow 초반부 자동 실행:
```
1. Read state.yaml
2. If session_count > 0:
   System message to LLM:
     "Previous session: {last_session_at}
      Last topic: {current_topic}
      Completed so far: {completed_topics}
      Upcoming: {upcoming_topics}

      Start with brief recap, then proceed."
```

### 진도 업데이트 패턴
세션 중 사용자·에이전트 상호작용에서 유의미한 진도가 있으면 state 업데이트.

```python
# 에이전트 내부 (Hermes가 처리)
async def update_state(agent_name: str, patch: dict):
    state_path = f"brain/session-state/{agent_name}/state.yaml"
    current = yaml.safe_load(await file.read(state_path)) or {}
    current.update(patch)
    await file.write(state_path, yaml.dump(current))
```

### 임시 flush (비정상 대비)
```python
async def periodic_flush():
    # 30초마다 backup
    await file.copy(state_path, state_path + ".bak")
```

---

## 5.5 Session Log의 KR 연결 (추가)

**원칙**: `state.yaml`은 clean (KR 매핑 없음). **세션 로그 개별 파일**의 프론트매터에 `kr_ref`.

이유:
- 세션이 여러 KR에 걸칠 수 있음 (예: ML 세션이 블로그 draft도 만듦)
- state 레벨에서 1개 KR로 묶으면 경직됨
- 로그 레벨에서 매칭하면 유연

### Session Log 프론트매터 예시

`brain/session-state/tutor-ml/logs/2026-04-19.md`:
```markdown
---
agent: tutor-ml
session_number: 12
date: 2026-04-19
duration_minutes: 45
topic: LoRA fine-tuning
kr_ref: 6.2                    # 주 기여 KR (선택)
kr_ref_secondary: [1.2]        # 부 기여 KR — 블로그 draft (선택)
---
```

**`kr_ref`는 선택 필드**. 에이전트가 세션 종료시 상황에 맞게 매칭. 없어도 OK.

### 주간 집계 (FR-D4 연계)

주간 리뷰가 이 `kr_ref`들을 스캔해 **KR별 세션 기여도** 집계:
- 예: KR 6.2 기여 세션 12개, 총 6시간 학습
- 예: KR 1.2 기여 세션 4개 (secondary 포함)

### 매칭 규칙

세션 종료시 세션 요약 생성하는 skill(`save-session-log`)이:
1. 세션 주제·결과물에서 KR 후보 추출
2. plan-tracker MCP `okr_kr_list(domain=agent.domain)`로 후보 조회
3. LLM으로 매칭 (confidence ≥ 0.6만)
4. 매칭 없으면 `kr_ref` 생략

---

## 6. 테스트 포인트

- [ ] 첫 세션 시작 → state.yaml 생성
- [ ] 두 번째 세션 → state 읽어와서 "지난번 X까지 했어요" 인사
- [ ] 세션 중간에 Hermes 비정상 종료 → `.bak`에서 복구
- [ ] state.yaml 수동 편집 → 다음 세션에 반영
- [ ] 세션 간 간격 길어도 state 유지 (1주, 1개월)
- [ ] logs/YYYY-MM-DD.md가 매 세션마다 생성
- [ ] **state.yaml에는 kr_ref 없음** (clean 유지)
- [ ] **세션 로그 프론트매터에 kr_ref가 필요할 때만 생성** (선택)
- [ ] **주간 리뷰가 kr_ref 스캔해 세션 기여 집계**
- [ ] plan-tracker MCP down 시 kr_ref 생략 (graceful)

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| state.yaml 문법 오류 | 파싱 실패 시 `.bak` 복구 시도, 실패 시 빈 state로 시작 (사용자 알림) |
| 진도 반영이 에이전트 해석에 의존 | 각 agent SKILL.md에 state 업데이트 지침 명확히 |
| 사용자가 state 수동 편집 후 혼란 | state 스키마 검증 + 유효성 에러 시 안내 |
| Hermes가 state 저장 실패 | MCP tool retries + 로그 |

---

## 8. 관련 FR

- **FR-E1** agent 구조 (state_path 필드)
- **FR-G1** 세션 요약 자동 저장 (logs/ 작성)
- **FR-E4** DIY — 새 workflow 추가 시 state 초기화

---

## 9. 구현 단계

- **Week 3 Day 5**: tools/sessions.py 기본
- **Week 3 Day 6**: MCP tool로 노출 (session_start/end)
- **Week 3 Day 7**: 임시 flush·복구
- **Week 4 Day 4~7**: 실사용 (1주 반복 세션으로 검증)
