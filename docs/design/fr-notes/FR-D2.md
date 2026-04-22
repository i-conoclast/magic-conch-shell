# FR-D2: 대화형 플랜 확정

**카테고리**: D. Planning
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

아침 브리핑(FR-D1) 응답으로 사용자가 말하면, **주고받는 대화**로 오늘 플랜 확정. 일방향 지시 아님.

---

## 2. 관련 컴포넌트

- **Skills**: `plan-confirm` (주)
- **Tools**: `memory`, `notion`, `llm`, `hermes`
- **의존**: 명시적 확정 명령, 중간 취소 허용

---

## 3. 데이터 플로우

```
아침 브리핑 후 사용자 응답 (iMessage)
   → Hermes가 응답 맥락이 "플랜 확정 중"임을 인식
   → plan-confirm skill 발동
   → 현재 플랜 목록 (브리핑에서 제안된 것) 기억
     - 각 항목에 OKR·KR 매칭 메타 함께 유지 (FR-D1에서 제공)
   → 대화 루프:
     사용자: "1번은 내일로, 블로그 초안 추가"
       → llm.call로 의도 파싱 → 플랜 업데이트
       → **신규 추가 항목은 자동으로 OKR·KR 매칭**:
         "블로그 초안" → O1 커리어 · KR 1.2 영문 블로그 12편
       → Hermes가 수정된 목록 응답 (KR 근거 포함)
     사용자: "OK"
       → 확정 아님. "'확정'이라고 명시해주세요"
     사용자: "확정"
       → memory.save_plan() + notion.create_tasks()
         - Notion Daily Tasks에 `KR` relation 필드 자동 채움
       → "3건 반영 완료 (KR 1.2, KR 1.4, ...)" 알림
```

---

## 4. 대화 패턴

```
시스템 (아침 브리핑): 오늘 우선순위 3 + 질문 1
  (각 항목에 KR 매칭 표시)

사용자: "1번 내일로. 블로그 초안 1시간 추가."

시스템: 업데이트된 오늘 목록:
  1. [~~Anthropic Jane follow-up~~] → 내일 (KR 1.4)
  2. ML 공부 2시간 (KR 6.2 · 논문 정리)
  3. 주간 리뷰 준비
  4. 블로그 초안 1시간 (신규 · KR 1.2 영문 블로그)
  계속 조정할까요, 확정할까요?

사용자: "블로그 30분으로 줄여. 확정."

시스템: 확정된 플랜 (KR 기여):
  1. ML 공부 2시간         → KR 6.2 +1 예상
  2. 주간 리뷰 준비
  3. 블로그 초안 30분       → KR 1.2 진도 유지
  4. (내일) Jane follow-up → KR 1.4
  ✓ Notion 반영 중...
  ✓ 3건 반영 완료 (KR 1.2, KR 6.2 연결).
```

---

## 5. 확정 조건 (strict)

**확정 트리거**: 명시적 키워드만
- "확정", "confirm", "이대로"

아닌 것 (애매):
- "오케이", "좋아", "OK" → 대화 계속

이유: **실수 확정 방지**.

---

## 6. 구현 노트

### SKILL.md
`skills/plan-confirm/SKILL.md`:
```markdown
---
name: plan-confirm
description: Interactive plan confirmation after morning brief. User can add/remove/modify items before explicit confirmation. Auto-matches new items to OKR/KRs.
trigger:
  - event: after_morning_brief_reply
  - command: /plan-confirm
tools: [memory, notion, llm, hermes]
model: codex-oauth
max_turns: 10
---

# Plan Confirm

## Flow
1. 현재 플랜 목록 로드 (오늘 daily의 morning brief 섹션, KR 매칭 포함)
2. 사용자 응답 수신
3. 의도 파싱 (추가·삭제·이동·수정·확정·취소)
4. 신규 추가시: OKR 컨텍스트(domain_okr_snapshot)로 KR 자동 매칭
5. 업데이트된 목록 표시 (KR 라벨 함께)
6. "확정" 명시까지 2~5 반복
7. 확정 시:
   - brain/plans/YYYY-MM-DD-*.md 저장 (확정 이력, kr_ref 필드 포함)
   - notion.create_page(Daily Tasks DB) — 각 항목, KR relation 필드 채움
   - 성공 알림 (연결된 KR 목록)
8. "취소" 시: 플랜 저장 안 함, 종료
```

### KR 자동 매칭 로직

```python
from tools import okr

async def match_to_kr(task_text: str) -> dict | None:
    """
    새 태스크를 OKR/KR에 자동 매칭 (plan-tracker MCP 경유).
    Return: {domain, objective, kr_id, kr_title, confidence} or None
    """
    # 1. 도메인 추정 (태스크 키워드)
    domain = infer_domain(task_text)

    # 2. plan-tracker MCP에서 해당 도메인 KR 목록 조회
    candidates = await okr.kr_list(domain=domain)
    if not candidates:
        return None  # plan-tracker down or no KRs

    # 3. LLM 매칭
    prompt = f"""
    Task: {task_text}
    Candidate KRs in {domain}:
    {render_kr_list(candidates)}

    Which KR does this task most directly advance? Return: {{kr_index: int | null, confidence: 0~1}}
    """
    result = await llm.call(prompt, model="ollama-local", response_format="json")
    if result["kr_index"] is not None and result["confidence"] >= 0.6:
        return candidates[result["kr_index"]]
    return None
```

### 상태 관리
대화 중 플랜 목록은 메모리 (Hermes conversational memory)에 유지. 명시 확정시만 영속 저장.

---

## 7. 테스트 포인트

- [ ] 3턴 이상 대화에서 맥락 유지
- [ ] "오케이" 입력 시 확정 안 됨
- [ ] "확정" 입력 시만 저장 + Notion push
- [ ] 대화 중 "취소" → 초기화
- [ ] 내일로 이동한 태스크가 다음날 브리핑에 반영
- [ ] Notion push 실패 시 로컬 큐 + 재시도
- [ ] **신규 추가 태스크가 적절한 KR에 자동 매칭** (예: "블로그 초안" → KR 1.2)
- [ ] **매칭 불확실 시 KR 미지정 허용** (confidence < 0.6)
- [ ] **Notion Daily Tasks의 KR relation 필드 자동 채움**
- [ ] **brain/plans/ frontmatter에 kr_ref 저장**
- [ ] 사용자가 KR 매칭을 수동 덮어쓰기 가능 (`-k 1.4` 옵션)

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 사용자 의도 파싱 오류 | 업데이트된 목록을 매 턴 보여줘 사용자 확인 |
| 대화 흐름이 엉켜 복잡해짐 | max_turns 10 + "처음부터" 명령 |
| Notion push 중 사용자가 나감 | 백그라운드 재시도, 다음 브리핑에 "어제 확정한 3건 반영 완료/실패" 안내 |

---

## 9. 관련 FR

- **FR-D1** 아침 브리핑 (진입점)
- **FR-D5** 외부 반영
- **FR-H1** Notion 쓰기

---

## 10. 구현 단계

- **Week 3 Day 2**: plan-confirm SKILL + 단순 대화
- **Week 3 Day 3**: 확정·Notion push 연결
- **Week 4 Day 4~7**: 실사용 튜닝
