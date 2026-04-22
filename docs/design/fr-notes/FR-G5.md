# FR-G5: 논리 비약 지적

**카테고리**: G. Evolution
**우선순위**: 중간 (MVP 포함)

---

## 1. Overview

사용자 결정에 **근거가 약하다** 판단되면 **챌린지 톤**으로 부드럽게 반문. 잔소리 금지. **논리 비약만** 범위.

---

## 2. 관련 컴포넌트

- **Skills**: `verify-plan` (hook agent — FR-D2에서 확정 직전)
- **Agents**: `planner`가 컨설팅 중 챌린지 삽입
- **Tools**: `memory.search` (대조 근거)

---

## 3. 범위 (매우 엄격)

### 지적 OK ✅
- **논리 비약**: "이거 하자" + 근거가 하나만 또는 없음
- 예: "Anthropic만 집중 지원" → "다른 회사 비교 없이 결정한 근거?"

### 지적 금지 ❌
- **뭉침**: 할 일 안 했다고 잔소리
- **과거 모순**: 지난번 A라 했는데 오늘 B — 지적 안 함 (생각 변한 것)
- **런라임**: 운동 3일 건너뛴 것 등 (부재 감지 nudge 금지)
- **작은 결정**: 점심 뭐 먹을지에 "근거 있어?" 금지

---

## 4. 대화 예시

**사용자** (플랜 확정 중): "이번 분기 Anthropic에만 집중 지원"

**시스템** (planner 챌린지):
> "집중 지원 결정 근거가 이번 달 Anthropic 면접 1건뿐인데, 다른 후보 회사와 비교 없이 확정해도 될까?
> - brain에는 OpenAI·Scale·Weights & Biases 관심 메모가 최근 있음
> 그래도 Anthropic만 집중하실 건가요?"

사용자 옵션:
- **그대로 진행**: "응, 집중" → 챌린지 수용, 확정
- **재검토**: 선택지 확장

---

## 5. 판단 로직

### Trigger
확정 직전 (plan-confirm 마지막 단계) + 컨설팅 응답 중 결정 도출 시점.

### 근거 약함 감지
```python
async def is_logic_weak(decision_text: str, context: dict) -> bool:
    """
    - 결정에 근거가 1개 이하?
    - 대안·비교 언급 없음?
    - brain/에 반대 근거 존재?
    """
    prompt = f"""
    Decision: {decision_text}
    Context from brain/: {context}

    Does this decision have sufficient reasoning?
    - Does it compare alternatives?
    - Does it cite specific evidence?
    - Are there contradicting signals in brain/?

    Return JSON: {{"is_weak": bool, "reason": str, "counter_evidence": [...]}}
    """
    result = await llm.call(prompt=prompt, model="codex-oauth")
    return result["is_weak"], result
```

---

## 6. verify-plan hook

`hooks/agent/verify-plan.md`:
```markdown
---
name: verify-plan
description: Validate plan coherence before Notion push — challenge if reasoning is weak
trigger:
  - event: pre-push
tools: [memory, llm]
isolation: fork
max_turns: 3
---

# Verify Plan

Given a confirmed plan, check:
1. Is reasoning weak? (is_logic_weak)
2. Are there conflicts with today's calendar?
3. Does it align with stated priorities (from USER.md or plan-tracker)?

Return: { status: "ok" | "challenge" | "block", reason?: string }

If "challenge": ask user once. User accepts → proceed. User reconsiders → return to plan-confirm.
If "block": hard block (e.g., duplicate push). Rare.
```

---

## 7. 비활성화 옵션

```bash
# 오늘만 챌린지 끔
mcs user add-rule "Disable challenges today"

# 도메인별
mcs user add-rule "No challenges in mental domain"
```

USER.md 에 반영:
```
## Manual Rules
- Disable challenges today (expires: 2026-04-19T23:59+09:00)
- No challenges in mental domain
```

---

## 8. 테스트 포인트

- [ ] 근거 약한 결정 → 챌린지 발동
- [ ] 사용자가 "그대로 진행" → 챌린지 수용, 확정
- [ ] 사용자가 재검토 → 선택지 확장
- [ ] 뭉침·부재는 챌린지 안 함
- [ ] USER.md에 비활성화 규칙 → 챌린지 skip
- [ ] 자주 무시되는 챌린지 패턴 → 빈도 감소 (학습)

---

## 9. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 챌린지가 잔소리처럼 느껴짐 | 톤 중요. "꼭 그렇게 하실 건가?" 가 아니라 "근거 확인해도 될까?" 수준. |
| 모든 결정에 챌린지 (피로) | 근거 약함 임계 + 도메인 제외 + 사용자 skip 쉽게 |
| 사용자 의도 오판 | "그대로 진행" 한 번이면 재챌린지 금지 |

---

## 10. 관련 FR

- **FR-D2** 플랜 확정 (챌린지 발동)
- **FR-F2** 컨설팅 톤 (챌린지 포맷)
- **FR-G4** 사용자 모델 (비활성화 규칙)

---

## 11. 구현 단계

- **Week 4 Day 1**: verify-plan hook 초안
- **Week 4 Day 2**: is_logic_weak 프롬프트 튜닝
- **Week 4 Day 4~7**: 실사용에서 오탐 조정
- **v1.0**: 더 정교한 감지 (학습 누적)
