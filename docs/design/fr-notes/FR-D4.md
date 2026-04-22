# FR-D4: 주간 리뷰

**카테고리**: D. Planning
**우선순위**: 중간 (MVP에 간소 버전 포함, 심화는 v1.0)

---

## 1. Overview

매주 일요일 20:00. 한 주 전체 회고 + 다음 주 제안. 1분 이내 생성.

---

## 2. 관련 컴포넌트

- **Skills**: `weekly-review`
- **Commands**: `/weekly`, `mcs weekly`
- **Tools**: `memory`, `notion`, `llm`

---

## 3. 데이터 플로우

```
Hermes cron 일요일 20:00 → /weekly
   → weekly-review skill
   → 데이터 수집:
     - 지난 7일 daily 파일들
     - notion.read_db(Daily Tasks, date range) 완료율
     - domain별 기록 수·활동량
     - 한 주간 활동 상위 엔티티
     - **plan-tracker MCP 호출**:
       - `okr_snapshot_current()` — 현재 OKR·KR
       - `okr_snapshot_history(weeks=1)` — 저번 주 스냅샷 (비교용)
     - plan-tracker down 시: domain analysis 섹션 생략, 실행 요약만
     - 한 주간 KR 변화 = plan-tracker history 직접 반환 (우리가 별도 저장 안 함)
   → 분석:
     - 도메인별 그룹핑 (Top3 활동·미달 영역)
     - KR 진도 vs 주간 목표 (quarter 목표 / 13주 = 주간 목표)
     - 뒤처진 KR 식별 (quarter 진도율 - 경과 시간 진도율)
     - 초과 달성 KR (리소스 재배분 여지)
   → llm.call(codex-oauth) 주간 리포트 생성
   → 저장: brain/daily/YYYY/MM/DD-weekly-review.md
     - domain_okr_weekly_history에 이번 주 스냅샷 저장 (다음 주 비교용)
   → iMessage 요약 전송
```

---

## 4. 리뷰 구성

```markdown
## Weekly Review — 2026-W16 (4/13~4/19)

### Execution
- 계획 21건 / 완료 17건 (81%)
- domain별 완료: career 7/8, ml 5/5, health-physical 3/4, relationships 1/2, finance 1/2

### Domain Analysis

#### 🟢 On Track
- **O6 ML 공부** — KR 6.2 논문 정리 50% → 63% (+13%)
  - 이번 주 3편 커버 (목표 주 1편 대비 초과)
- **O2 건강(신체)** — KR 2.1 주 3회 운동 ✅ 4/3 (133%)

#### 🟡 Caution
- **O1 커리어** — KR 1.2 영문 블로그 3편 → 3편 (변화 없음, 주간 목표 1편 미달)
  - draft 1개는 있으나 발행 없음
- **O5 재무** — KR 5.3 비상금 적립 55% → 60% (+5%, 주간 목표 +7% 미달)

#### 🔴 Behind
- **O3 멘탈** — KR 3.1 번아웃 신호 제로: 이번 주 수면 4.5h일 2회 기록 → 위험

### Highlights
- Anthropic 1차 면접 완료 (KR 1.4 진도 +1)
- LoRA 구현 복습 + 블로그 초안 (KR 6.2, KR 1.2 동시 기여)

### Active entities
- people/jane-smith (3 interactions)
- companies/anthropic (3 records)

### Next week suggestions (KR 정렬)
1. **블로그 #1 발행 (밀린 KR 1.2)** — 주간 2시간 블록 확보
2. **수면 관리 (KR 3.1 위험)** — 취침 시간 22:30 원칙
3. Jane follow-up (4/25 전, KR 1.4)
4. 건강 체크업 예약 (KR 2.3)

### Pattern detected
- 주말 학습 세션 거절률 ↑ (4회 중 3회 거절). 주중으로 이동?
- 블로그 초안 단계 정체 (2주째 draft → 발행 없음). 발행 목표 주 1편 재확인?
```

---

## 5. SKILL.md

```markdown
---
name: weekly-review
description: Weekly review every Sunday 20:00 KST. Aggregates execution, domain OKR progress, entity highlights, and next-week suggestions grounded in KR status.
trigger:
  - cron: "0 20 * * 0"
  - command: /weekly
tools: [memory, notion, llm]
model: codex-oauth
timeout: 60
---

# Weekly Review

Aggregate last 7 days:
1. memory.daily × 7
2. notion.read_db(Daily Tasks, range) → 완료율 + 도메인별
3. memory.entity_activity(since="7 days ago") → 상위 엔티티
4. okr.snapshot_current() (plan-tracker MCP) → 현재 OKR·KR
5. okr.snapshot_history(weeks=1) (plan-tracker MCP) → 저번 주 스냅샷

Analyze by domain bucket:
- On Track (quarter 진도 ≥ 경과 시간 비율)
- Caution (진도 -10~0%)
- Behind (진도 < -10%)

Generate markdown report with:
- Execution completion + domain breakdown
- 3-bucket Domain Analysis (On Track / Caution / Behind)
- Highlights tying activities to KR progress
- Active entities
- Next week suggestions aligned with behind KRs first
- Detected patterns (laggards, rejections)

Save to brain/daily/YYYY/MM/DD-weekly-review.md.
(History 비교는 plan-tracker가 보관하므로 mcs 측에는 별도 저장 불필요.)
Send summary via iMessage.
```

---

## 6. 테스트 포인트

- [ ] 일요일 20:00 자동 트리거
- [ ] 7일 데이터 집계 정확
- [ ] 리포트 1분 이내 생성
- [ ] brain/daily/.../YYYY-MM-DD-weekly-review.md 저장
- [ ] iMessage로 요약 도착
- [ ] **7 도메인 각각이 On Track / Caution / Behind 3 버킷으로 분류**
- [ ] **plan-tracker MCP `okr_snapshot_history(weeks=1)`로 주간 변화 표시**
- [ ] **Next week suggestions가 Behind·Caution KR을 우선 반영**
- [ ] **plan-tracker MCP 다운 시 graceful degrade** — 실행 요약만 출력
- [ ] 첫 주에는 history 비교 대상 없어도 단순 포맷으로 저하 가능

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 데이터 부족한 주 (첫 주) | 최소 포맷으로라도 생성, history 비교 섹션은 생략 |
| 너무 긴 리포트 | iMessage는 요약, 전체는 파일로 |
| OKR 진도 읽기 실패 | plan-tracker와 경계 준수, 실패 시 해당 섹션 생략 |
| **버킷 경계가 자의적** | 기준 공개 (±10%), 사용자가 USER.md에서 조정 가능 |
| **plan-tracker MCP 다운** | OKR 없이 실행 요약만 리포트. 나중에 보강 가능. |
| **quarter 중간 시점에 평가** | "경과 시간 비율" 계산 (주차 / 13주)으로 공정하게. plan-tracker가 계산해서 반환. |

---

## 8. 관련 FR

- **FR-D1** 아침 브리핑 (유사 로직)
- **FR-G4** 사용자 모델 (패턴 감지 결과 반영)
- **FR-H2** Notion 읽기

---

## 9. 구현 단계

- **Week 4 Day 1**: weekly-review SKILL.md
- **Week 4 Day 3**: cron 등록 + 실행 테스트
- **v1.0**: 심화 분석 (trend·forecast)
