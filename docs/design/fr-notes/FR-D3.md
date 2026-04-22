# FR-D3: 저녁 회고 (대화형)

**카테고리**: D. Planning
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

매일 22:00 저녁 회고. 하루 회고 + **오늘 쌓인 승인 인박스** 일괄 처리. 5분 이내.

---

## 2. 관련 컴포넌트

- **Skills**: `evening-retro` (주)
- **Commands**: `/retro`, `mcs retro`
- **Tools**: `memory`, `notion`, `llm`, `hermes`
- **연계**: FR-C2 (엔티티 승인), FR-E5 (스킬 승격), FR-G3 (제안 인박스)

---

## 3. 데이터 플로우

```
Hermes cron 22:00 → /retro 트리거
   → evening-retro skill
   → Phase 0: 컨텍스트 수집
     - okr.snapshot_current() (아침 캐시 재사용 or plan-tracker MCP 재호출)
     - plan-tracker down 시 KR 기여 섹션 생략 (graceful)
   → Phase 1: 오늘 실행 확인
     - notion.read_db(Daily Tasks, date=today) 완료/미완료
     - brain/daily/.../DD.md 엔트리 수집
     - 오늘 확정 플랜 vs 실제 비교
     - **KR 기여 집계**: 오늘 완료된 태스크 (brain/plans frontmatter.kr_ref)
       → plan-tracker snapshot의 현재값과 대조
     - **KR before/after 비교** (아침 스냅샷 vs 저녁 스냅샷)
   → Phase 2: 승인 인박스 처리
     - state.get_approval_inbox()
     - 각 항목 (entity-draft, skill-promotion, suggestion) 사용자에게 제시
     - 사용자 응답 → 승인/거절/내일
   → Phase 3: 느낀 점·배운 점 (선택)
     - 빈칸이어도 OK
   → Phase 4: 내일 메모 (선택)
     - 뒤처진 KR 1~2개 힌트 제공 (내일 우선순위 기반)
   → 저장
     - brain/daily/.../DD.md 🌙 Evening Retro 섹션 append (KR 변화 포함)
     - 승인된 항목 처리 (엔티티 이동·스킬 확정·제안 실행)
```

---

## 4. 대화 예시 (iMessage)

```
🌙 저녁 회고 (5분)

Phase 1 — 오늘 실행
  완료: 3/5
  - [x] ML 공부 2시간       → KR 6.2 +1 (2편 → 3편, 50%→63%)
  - [x] 주간 리뷰 준비
  - [x] 블로그 초안 30분     → KR 1.2 진행 (3편 → 3편 + draft)
  - [ ] Jane follow-up 메일 (내일?)
  - [ ] 운동 1시간 (내일?)

  오늘 KR 기여: KR 6.2 +1, KR 1.2 draft 진행.
  미완료 둘은 내일로 옮길까요, 드롭할까요?

사용자: 둘 다 내일로

  ✓ 내일 오전 슬롯 제안.

Phase 2 — 승인 3건
  1. 새 인물: Jane Smith (ML Recruiter @ Anthropic)
     [승인] [거절] [내일]

사용자: 승인

  2. 스킬 승격 제안: "주간 지출 회고" 패턴 4회
     [승인] [거절] [내일]

사용자: 내일

  3. 제안: Jane과 마지막 접촉 9일 전. 내일 follow-up 우선순위?
     [수용 — 내일 플랜에 추가] [거절] [나중]

사용자: 수용

Phase 3 — 느낀 점 한 줄?

사용자: 블로그 재미. 꾸준히 하고 싶음.

Phase 4 — 내일 메모?

  뒤처진 KR 참고:
  - KR 5.3 비상금 적립 60% (이번달 목표 대비 -15%)
  - KR 2.1 주간 운동 3회 2/3 (오늘 미완, 내일 필요)

사용자: (pass)

  ✓ 회고 저장.
  Goodnight 🌙
```

---

## 5. SKILL.md

`skills/evening-retro/SKILL.md`:
```markdown
---
name: evening-retro
description: Evening review at 22:00 KST. Combines today's execution check, approval inbox processing, and optional reflection
trigger:
  - cron: "0 22 * * *"
  - command: /retro
tools: [memory, notion, llm, hermes]
model: ollama-local  # 로컬 OK (빈도 높음, 품질 덜 민감)
max_turns: 20
---

# Evening Retro

## Flow

Phase 1: Execution check
  - notion.read_db(Daily Tasks where date=today)
  - Compare with morning brief plan (brain/daily/today)
  - Present completed/uncompleted, ask what to do with uncompleted

Phase 2: Approval inbox
  - memory_get_approval_inbox()
  - For each item, present + get decision (approve/reject/defer)

Phase 3: Reflection (optional)
  - Ask for one-line feeling/learning

Phase 4: Tomorrow memo (optional)

Save:
  - brain/daily/YYYY/MM/DD.md append 🌙 section
  - Process approved items (entity confirm, skill promotion, suggestion actions)
```

---

## 6. 테스트 포인트

- [ ] 22:00 cron 자동 트리거
- [ ] Phase 1에서 Notion 완료 상태 정확 반영
- [ ] Phase 2 인박스 항목이 모두 제시됨
- [ ] "내일"로 미룬 항목이 다음 회고에 재등장
- [ ] 건너뛴 Phase는 빈 상태로 저장 (에러 없음)
- [ ] 전체 세션 5분 이내 완료 가능
- [ ] **KR 기여 집계 표시** — 오늘 완료 태스크가 어느 KR에 +N
- [ ] **KR before/after 비교** — 아침 수치 대비 저녁 수치 변화
- [ ] **Phase 4에 뒤처진 KR 힌트** — 이번달 목표 대비 어긋난 KR 1~2개 제시
- [ ] brain/daily/.../DD.md 🌙 섹션에 **KR 변화 기록**

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 사용자 회고 건너뜀 | 다음 아침 브리핑에 "승인 N건 대기" 안내 |
| 승인 항목 너무 많음 | Phase 2에서 상위 5개만, 나머지는 `mcs approval-inbox` 명령 |
| Ollama 응답 지연 | 복잡 의사결정은 Codex로 escalate 옵션 |
| 회고 기록 삭제 (사용자 실수) | brain/ 파일은 git처럼 백업 권장 |

---

## 8. 관련 FR

- **FR-C2** 엔티티 승인
- **FR-E5** 스킬 승격 승인
- **FR-G3** 제안 인박스
- **FR-B3** 하루 뷰 (retro 섹션 저장)

---

## 9. 구현 단계

- **Week 3 Day 6**: evening-retro SKILL.md 초안
- **Week 3 Day 7**: Phase 1~4 흐름
- **Week 4 Day 2**: Hermes cron 등록
- **Week 4 Day 4~7**: 실사용 튜닝
