# FR-F4: 동일 오라클 답 연속 방지 (streak)

**카테고리**: F. Voice & Tone
**우선순위**: 중간 (MVP 포함)

---

## 1. Overview

같은 오라클 답이 **3회 연속**이면 다음은 컨설팅/하이브리드 톤 강제. 오해로 가벼운 답 반복되는 상황 방지.

---

## 2. 관련 컴포넌트

- **State**: `.brain/streak-state.json`
- **Skills**: `conch-answer` 내부 로직
- **Tools**: state R/W

---

## 3. Streak State

`.brain/streak-state.json`:
```json
{
  "recent_responses": [
    {"ts": "2026-04-19T10:00:00+09:00", "tone": "oracle", "answer": "No."},
    {"ts": "2026-04-19T10:15:00+09:00", "tone": "oracle", "answer": "Nothing."},
    {"ts": "2026-04-19T10:30:00+09:00", "tone": "oracle", "answer": "No."}
  ],
  "same_answer_streak": 1,
  "oracle_streak_any": 3,
  "last_forced_to_planner": null
}
```

---

## 4. 판단 로직

```python
def check_streak(recent: list[dict], new_candidate_answer: str | None = None) -> dict:
    """
    Returns: {
        "force_planner": bool,
        "reason": str,
    }
    """
    # 같은 답 3회 연속
    last_3 = recent[-3:]
    if len(last_3) == 3 and all(r["tone"] == "oracle" for r in last_3):
        if len(set(r["answer"] for r in last_3)) == 1:
            return {"force_planner": True, "reason": "same oracle answer 3x"}

        # 다른 답이지만 oracle만 5회 연속이면 강제 (설정 가능)
        last_5 = recent[-5:]
        if len(last_5) == 5 and all(r["tone"] == "oracle" for r in last_5):
            return {"force_planner": True, "reason": "oracle streak 5"}

    return {"force_planner": False, "reason": ""}
```

---

## 5. 강제 전환 UX

```
사용자: (계속 가벼운 질문)
시스템: Nothing.  (1회)
사용자: ...
시스템: Nothing.  (2회)
사용자: ...
시스템: Nothing.  (3회 — streak 감지)
사용자: 다음 질문
시스템: (planner 톤 강제)
  "진짜 뭔가 찾고 있는 건가요? 오늘 일정/기록 기반으로 제안:
   - Option A: ...
   - Option B: ..."
```

---

## 6. 사용자 설정

`USER.md` 의 manual rules:
```markdown
- Streak prevention: off
- Allow oracle streak up to 10 (default 3)
```

→ state에 반영되어 판단 함수가 임계 조정.

---

## 7. 구현 노트

```python
# conch-answer 내부
async def respond(query: str) -> dict:
    streak = await state.read("streak-state.json")
    check = check_streak(streak["recent_responses"])

    if check["force_planner"]:
        tone = "planner"
    else:
        tone = select_tone(query, ...)  # FR-F1

    answer = await _generate_response(query, tone)

    # state 업데이트
    streak["recent_responses"].append({
        "ts": now_kst().isoformat(),
        "tone": tone,
        "answer": answer[:100],  # 일부
    })
    streak["recent_responses"] = streak["recent_responses"][-10:]  # 최근 10개만
    await state.write("streak-state.json", streak)

    return {"tone": tone, "answer": answer}
```

---

## 8. 테스트 포인트

- [ ] 같은 답 3회 연속 → 4번째 planner 강제
- [ ] 다른 oracle 답 5회 연속 → 6번째 planner 강제 (설정 시)
- [ ] 중간에 planner·hybrid 답 끼면 카운터 리셋
- [ ] 사용자 설정으로 streak 비활성화 가능
- [ ] state 파일 손상 시 초기화 + 정상 동작

---

## 9. 리스크·완화

| 리스크 | 완화 |
|---|---|
| state 파일 손상 | 손상 감지 시 빈 state로 초기화 |
| 사용자가 장난 이어가고 싶음 | 사용자 설정으로 off 가능 |
| 임계값 부적절 | 사용 후 조정 (USER.md 반영) |

---

## 10. 관련 FR

- **FR-F1** 톤 판단 (주 로직)
- **FR-F3** 오라클 톤 (차단 대상)
- **FR-G4** 사용자 모델 (설정)

---

## 11. 구현 단계

- **Week 2 Day 6**: streak state + 체크 함수
- **Week 2 Day 7**: conch-answer 통합
- **Week 4 Day 4~7**: 실사용에서 임계 조정
