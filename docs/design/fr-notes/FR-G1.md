# FR-G1: 세션 요약·로그 자동 저장

**카테고리**: G. Evolution
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

모든 에이전트 상호작용(플래닝·회고·세션·자유 대화) **종료 시 자동 요약 + 로그 저장**. 사용자 명시 불필요.

---

## 2. 관련 컴포넌트

- **Tools**: `memory.save_session_log`
- **Hooks**: `post_agent_session` (선택)
- **Skills**: 각 session-generating skill이 내장 호출
- **State**: `brain/session-state/{agent}/logs/`

---

## 3. 데이터 플로우

```
agent session ends (정상 or 타임아웃)
   → hermes가 종료 이벤트 발생
   → post_agent_session hook (또는 agent flow 마지막 단계)
   → llm.call로 요약 생성:
     - 주요 결정·결론
     - 다음 할 일
     - 배운 점
   → 저장:
     - brain/session-state/{agent}/logs/YYYY-MM-DD.md
     - state.yaml 갱신 (FR-E3)
   → memsearch 인덱싱 자동 (live sync)
```

---

## 4. 로그 포맷

```markdown
---
agent: tutor-english
session_number: 9
date: 2026-04-19
started_at: 2026-04-19T19:30:00+09:00
ended_at: 2026-04-19T19:55:00+09:00
duration_minutes: 25
topic: Past perfect tense
vocabulary_new: [had been, by the time]
---

## Summary
Covered past perfect usage via yesterday's story. User handled most forms well. Article errors remain (a/the).

## Decisions / Next
- Next session: Conditional sentences (1st and 2nd)
- Additional drill: articles worksheet

## Observations
- Pace: good
- Engagement: high
- Struggle: article choice in complex sentences
```

---

## 5. 저장 실패 복구

- 로그 생성 중 LLM 실패 → 최소 메타만 저장 (duration, date)
- 저장소 접근 실패 → 임시 파일 `.brain/pending-logs/` → 복구 후 정본으로

---

## 6. 구현 노트

```python
# tools/memory.py
async def save_session_log(agent_name: str, transcript: list[dict]) -> dict:
    # 요약 생성
    prompt = render_summary_prompt(transcript)
    summary = await llm.call(prompt=prompt, model="ollama-local", max_tokens=400)

    # 로그 파일
    today = date.today().isoformat()
    log_path = f"brain/session-state/{agent_name}/logs/{today}.md"
    meta = {
        "agent": agent_name,
        "date": today,
        "started_at": transcript[0]["ts"],
        "ended_at": transcript[-1]["ts"],
        "duration_minutes": calc_duration(transcript),
        "session_number": await _next_session_number(agent_name),
    }
    body = format_summary_body(summary, transcript)
    await file.write(log_path, assemble(meta, body))

    return {"path": log_path, "summary": summary}
```

---

## 7. 테스트 포인트

- [ ] 세션 종료 → log 파일 자동 생성
- [ ] 요약이 핵심 결정·결론 포함
- [ ] 25분 세션 → duration 정확
- [ ] state.yaml session_count++
- [ ] LLM 실패해도 메타는 저장
- [ ] memsearch 인덱스에 등장 (몇 분 내)
- [ ] 저녁 회고에서 오늘 세션 로그 참조 가능

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 로그가 너무 길어짐 (긴 대화) | 요약은 400토큰 상한 |
| 요약 품질 낮음 (LLM) | ollama-local → 필요 시 codex-oauth 재시도 |
| 저장 실패 | 임시 폴더 + 재시도 |
| 민감 대화 내용 | transcript 전체 저장 전 필터링 옵션 |

---

## 9. 관련 FR

- **FR-E3** 진도 승계 (state 갱신)
- **FR-D3** 저녁 회고 (로그 참조)
- **FR-B1** 검색 (로그 포함)
- **FR-G2** 자동 태깅 (로그도 엔티티 감지 대상)

---

## 10. 구현 단계

- **Week 3 Day 5**: save_session_log 함수
- **Week 3 Day 6**: 요약 프롬프트 튜닝
- **Week 3 Day 7**: 세션 종료 훅 연결
