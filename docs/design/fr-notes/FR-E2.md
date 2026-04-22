# FR-E2: 명시적 호출 + 자동 트리거 하이브리드

**카테고리**: E. Sessions
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

workflow(agent) 진입 방법 **2가지**:
1. **명시적 호출**: `/english` 또는 `mcs english`
2. **자동 감지**: 사용자 메시지 맥락이 특정 agent와 관련돼 보이면 "전환할까요?" 제안

---

## 2. 관련 컴포넌트

- **Commands**: `commands/english.md` 등
- **Skills**: `conch-answer` (자동 감지 로직 포함)
- **Tools**: `hermes` (subagent spawn)

---

## 3. 데이터 플로우

### 명시적 호출
```
사용자: /english
   → Hermes command 라우팅 → agents/tutor-english.md 로드
   → subagent(isolation=fork) 시작
```

### 자동 감지
```
사용자: "요즘 LoRA 구현 복습 중이야"
   → Hermes가 메시지 수신
   → conch-answer skill 발동 (주 응답자)
   → conch-answer이 메시지 분석:
     - 키워드: "LoRA", "복습"
     - 매치 가능 agent: tutor-ml
     - 신뢰도: 0.8
   → 사용자에게 확인:
     "ML 공부 세션으로 전환할까요?"
   → 승인 → tutor-ml agent 호출
   → 거절 → 범용 응답으로 이어짐
```

---

## 4. 자동 감지 로직

### conch-answer SKILL.md 일부
```
## Agent routing

Before answering directly, check if the message matches a workflow agent:

1. Collect agent descriptions from agents/
2. LLM call: "Does this message match any agent's description?"
   Input: user message + agent descriptions
   Output: {matched: slug or null, confidence: 0~1, reason: ...}
3. If matched and confidence >= 0.7:
   - Ask user: "Switch to {agent_name} session?"
   - On yes: hermes.spawn_subagent(slug)
   - On no: continue with conch-answer
4. Else: continue with conch-answer
```

### 키워드 힌트 (빠른 경로)
```python
AGENT_KEYWORDS = {
    "tutor-english": ["영어", "english", "conversation", "practice"],
    "tutor-ml": ["ml", "머신러닝", "딥러닝", "learning", "논문"],
    "interviewer": ["면접", "인터뷰", "mock interview"],
    "advisor-finance": ["재무", "finance", "투자", "포트폴리오", "리밸런싱"],
}

def quick_match(message: str) -> str | None:
    msg_lower = message.lower()
    for agent, kws in AGENT_KEYWORDS.items():
        if any(kw in msg_lower for kw in kws):
            return agent
    return None
```

빠른 경로가 매치되면 LLM 확인 전 사용자에게 빠르게 제안. 애매하면 LLM 거침.

---

## 5. 이탈·취소

세션 중 언제든:
- "그만" / "종료" / "exit" → 세션 종료, 범용 모드로
- 명시 명령: `/exit-session`

```python
# agent 프론트매터에 자동 포함 (Hermes 표준)
exit_commands: [그만, 종료, exit, stop]
```

---

## 6. 테스트 포인트

- [ ] `/english` → 즉시 세션 진입
- [ ] "LoRA 복습 중" → tutor-ml 제안 (자동)
- [ ] 자동 제안 거절 → 범용 응답 이어짐
- [ ] 세션 중 "그만" → 종료
- [ ] 빠른 경로(키워드) 히트 시 LLM 호출 없이 제안
- [ ] 여러 agent 매치될 때 가장 높은 신뢰도 선택 또는 사용자 선택
- [ ] false positive 낮음 (관련 없는데 제안되지 않음)

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 자동 제안 오탐 | 신뢰도 ≥ 0.7 + 사용자 확인 필수 |
| 제안 피로 (너무 자주) | 최근 거절한 제안 기억, 동일 패턴 반복 시 제안 skip |
| 빠른 경로 키워드 누락 | LLM fallback으로 안전망 |
| 세션 이탈 못함 | 표준 exit 명령 여러 개 등록 |

---

## 8. 관련 FR

- **FR-E1** agent 정의
- **FR-F1** 톤 판단 (conch-answer 내부)
- **FR-E3** 진도 승계

---

## 9. 구현 단계

- **Week 2 Day 6**: conch-answer SKILL.md에 agent routing 섹션
- **Week 3 Day 5**: 빠른 경로 + LLM fallback
- **Week 3 Day 6**: 자동 제안 UX 튜닝
