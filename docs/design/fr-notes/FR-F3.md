# FR-F3: 오라클 톤 (가벼움)

**카테고리**: F. Voice & Tone
**우선순위**: 중간 (MVP 포함)

---

## 1. Overview

가벼운 질문에 **한 줄 단호** 응답. "The shell has spoken" 스타일.

---

## 2. 관련 컴포넌트

- **Agents**: `oracle` (전용 퍼소나)
- **Data**: `skills/conch-answer/oracle-dictionary.md` (사전)
- **Tools**: 거의 없음 — 사전 조회만. LLM 거의 안 씀.

---

## 3. Oracle Dictionary

`skills/conch-answer/oracle-dictionary.md`:
```markdown
# Oracle Dictionary

## Original (SpongeBob Magic Conch)
- No.
- Nothing.
- Maybe someday.
- Yes.
- The shell has spoken.

## Custom
- 소라고둥은 답하지 않는다.
- Try asking again.
- 당연히 그렇다.
- Not today.
- The shell is tired.
- Ask tomorrow.
- 소라고둥이 고개를 젓는다.
- ...   (침묵 응답, 3초 지연 후 빈 답)

## Usage rules
- 가벼운 질문에 무작위 선택
- Streak 방지 (FR-F4): 같은 답 3회 연속 금지
- 사용자 편집 가능 — 본인 톤 반영
```

---

## 4. oracle agent

`agents/oracle.md`:
```markdown
---
name: oracle
description: Light-question conch responder. One line. No reasoning. Playful.
tools: []    # LLM도 최소 사용 — 대부분 사전 조회
isolation: shared
---

# Oracle

## Persona
I am the shell. I speak in single lines.
Questions get answers from my dictionary.
No explanations. No apologies.

## Steps
1. Read oracle-dictionary.md
2. Filter out recently-used answers (last 2)
3. Pick one randomly (weighted if user preferences)
4. Return. Done.

## Rules
- ONE LINE ONLY
- No "I think", no "probably", no elaboration
- No emoji (unless dictionary entry has one)
- If user persists with serious undertone, force planner (FR-F4)
```

---

## 5. 응답 예시

```
사용자: 뭐 재미있는 거 없어
시스템: Nothing.

사용자: 지금 뭐 하지
시스템: Maybe someday.

사용자: 내일 날씨
시스템: 소라고둥은 답하지 않는다.

사용자: OK 그럼 진지하게 내일 일정
시스템: (planner 톤으로 전환)
  내일 일정:
  - 09:00 ML 공부 (by config)
  - 14:00 Anthropic 2차 예정
  ...
```

---

## 6. 구현 노트

```python
async def oracle_respond(query: str, recent_answers: list[str]) -> str:
    dictionary = await file.read_dictionary("oracle-dictionary.md")
    candidates = [d for d in dictionary if d not in recent_answers[-2:]]
    if not candidates:
        candidates = dictionary  # fallback
    return random.choice(candidates)
```

사전은 프론트매터 없는 단순 리스트. LLM 호출 없음.

---

## 7. 테스트 포인트

- [ ] 가벼운 질문 → 한 줄 응답
- [ ] 사전의 답만 나옴 (LLM이 새로 생성 안 함)
- [ ] 같은 답 3회 연속 안 나옴 (FR-F4 연계)
- [ ] 사용자가 사전 편집 시 다음 응답에 반영
- [ ] 응답 1초 이내 (LLM 없음)

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 너무 반복적이라 싫증 | 사전 확장 (사용자 추가) + streak 방지 |
| 진지한데 가벼운 걸로 오판 → oracle 응답이 부적절 | FR-F4 streak + 사용자 "진지하게" 재요청 |
| 응답이 안 맞는 맥락 (예: 질문 아닌데) | 질문 여부 사전 체크 |

---

## 9. 관련 FR

- **FR-F1** 톤 판단
- **FR-F4** Streak 방지
- **FR-G4** 사용자 모델 (사전 커스터마이즈)

---

## 10. 구현 단계

- **Week 2 Day 4**: oracle-dictionary.md 초기 사전
- **Week 2 Day 5**: oracle agent + 응답 로직
- **Week 4 Day 4~7**: 실사용 후 사전 확장
