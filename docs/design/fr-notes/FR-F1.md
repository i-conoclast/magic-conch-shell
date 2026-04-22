# FR-F1: 상황별 톤 자동 판단

**카테고리**: F. Voice & Tone
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

사용자 질의의 **성격**을 분석해 컨설팅 / 오라클 / 하이브리드 톤을 자동 선택. 사용자가 명시할 필요 없음.

---

## 2. 관련 컴포넌트

- **Skills**: `conch-answer` (주 — 모든 질의 라우팅)
- **Tools**: `memory` (brain_hits 판단용)
- **의존**: SOUL.md 톤 규칙

---

## 3. 판단 로직

```python
def select_tone(query: str, brain_hits_count: int, streak_info: dict) -> str:
    """
    Returns: "planner" | "oracle" | "hybrid"
    """
    # 1. Streak 방지 (FR-F4) 우선
    if streak_info.get("force_planner", False):
        return "planner"

    # 2. 진지 도메인 키워드 매치
    if has_serious_keywords(query):
        return "planner"

    # 3. 가벼운 키워드 + brain에 관련 기록
    if has_light_keywords(query) and brain_hits_count >= 3:
        return "hybrid"

    # 4. 가벼운 키워드 + 기록 없음
    if has_light_keywords(query):
        return "oracle"

    # 5. 애매 → planner (기본 보수)
    return "planner"
```

---

## 4. 키워드 사전

### Serious (컨설팅 톤)
```
career:  면접, 이력서, 연봉, 오퍼, 지원, 포트폴리오
health:  운동, 수면, 식단, 건강, 병원, 약
finance: 투자, 주식, 자산, 지출, 저축, 리밸런싱
mental:  기분, 스트레스, 번아웃, 우울, 불안
ml:      공부, 논문, 실험, 구현, 학습
relationships: 가족, 파트너, 친구, 관계, 대화
meta:    결정, 선택, 우선순위, 목표, KR, OKR, 계획
```

### Light (오라클 톤)
```
점심, 저녁, 뭐 먹지, 뭐 하지, 심심, 재미있, 지루, 놀까, 간식,
뭐 해, 날씨, 오늘 기분, 커피, 어때
```

### 판단 우선순위
**serious > light**. 둘 다 있으면 serious. (예: "점심 전에 면접 준비" → serious)

---

## 5. conch-answer SKILL.md

`skills/conch-answer/SKILL.md`:
```markdown
---
name: conch-answer
description: Primary message router. Detects tone (consulting / oracle / hybrid) and routes to appropriate response style. Handles all incoming queries.
trigger:
  - event: on_message
tools: [memory, llm]
model: ollama-local  # 판단은 빠르고 싸게
max_turns: 1  # 판단 단일 턴
---

# Conch Answer

## Role
Every message comes through me first. I decide the tone.

## Steps

1. Check streak_state (state.json) — if last 3 oracle answers same, force planner
2. Check agent routing (FR-E2) — if workflow match, propose transition instead
3. Score query:
   a. serious keywords present? → planner
   b. brain_hits >= 3 + light keywords? → hybrid
   c. light keywords only? → oracle
   d. ambiguous? → planner (default)
4. Return tone decision + route to appropriate skill/agent

## Tools
- memory.search(query, top_k=3) to count brain_hits

## References
- [keyword-dict.md](keyword-dict.md)
- [SOUL.md](../../SOUL.md) for tone rules
```

---

## 6. 테스트 포인트

- [ ] "ML 방향 맞아?" → planner (진지 키워드)
- [ ] "점심 뭐 먹지" + 식사 기록 5건 → hybrid
- [ ] "점심 뭐 먹지" + 식사 기록 없음 → oracle
- [ ] "뭐 할지 결정" → planner (meta 키워드)
- [ ] "Jane 연락해야 하나?" + Jane 엔티티 → planner (entity 기반)
- [ ] 연속 3회 같은 oracle 답 → 다음 쿼리 planner 강제 (FR-F4)
- [ ] 사용자가 "진지하게 답해줘" → 다음 응답은 planner

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 키워드 사전 누락 → 오판 | 사용자 모델(USER.md)에 본인 키워드 추가 가능 |
| LLM 기반 판단 느림 | 키워드 기반 빠른 판단 우선, 애매할 때만 LLM |
| 문맥 놓침 (예: 앞 대화 이어가는 질문) | conversational memory 활용 (Hermes) |

---

## 8. 관련 FR

- **FR-F2** 컨설팅 톤 구현
- **FR-F3** 오라클 톤 구현
- **FR-F4** Streak 방지
- **FR-E2** agent routing (상위 로직)

---

## 9. 구현 단계

- **Week 2 Day 4**: 키워드 사전 + 판단 함수
- **Week 2 Day 5**: conch-answer SKILL.md
- **Week 2 Day 6**: Hermes에서 on_message 트리거 등록
