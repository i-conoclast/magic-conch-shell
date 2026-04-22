# FR-E5: 자동 스킬 승격 (승인 필요)

**카테고리**: E. Sessions
**우선순위**: 중간 (MVP 간소 버전, 심화는 v1.0)

---

## 1. Overview

사용자가 **반복하는 상호작용 패턴**을 시스템이 감지해 "이걸 workflow로 저장할까요?"라고 제안. 승인 시 초안 생성.

**MVP 범위**: Hermes 내장 `skill_manage` 기능 활용. 최소 제안 로직.

---

## 2. 관련 컴포넌트

- **Hermes 내장**: skill_manage (자체 승격 기능)
- **우리 측**: `approval-inbox` 통합, `skills/drafts/` 경로
- **Skills**: `evening-retro` 내 제안 처리
- **Tools**: `memory.promote_pattern`

---

## 3. 감지 로직 (MVP 간소)

```
매주 주간 리뷰 시 (cron 일요일 20:00)
   → 지난 7일 대화 로그 분석
   → 비슷한 대화 흐름이 N회 (기본 3) 이상 반복됐나?
     - 같은 키워드 집합 + 같은 질문 패턴
   → 조건 충족 시 제안 생성
     → approval-inbox에 "skill-promotion" 항목 추가
   → 저녁 회고에서 사용자에게 제시
     → 승인 → skills/drafts/{suggested-name}/SKILL.md 생성
     → 사용자가 편집·확정 → skills/로 이동
```

v1.0에서는 Hermes의 자체 감지 기능 더 활용.

---

## 4. 제안 예시

주간 리뷰 결과:
```
## Patterns detected

1. "이번 주 지출 얼마" → 카테고리별 정리 → 다음 주 예산 조정
   (4회 반복, 매주 일요일 저녁)
   Proposed: skill weekly-spending-review
   [승인 — 초안 생성] [거절] [내일]

2. (없음)
```

승인 시 자동 생성:
```
skills/drafts/weekly-spending-review/
└── SKILL.md  (Hermes가 감지한 흐름 기반 초안)
```

```markdown
---
name: weekly-spending-review
description: Weekly spending category review — detected from repeated conversation pattern (4 times over 4 weeks)
trigger:
  - cron: "0 21 * * 0"    # 일요일 21:00
  - command: /spending
tools: [notion, memory, llm]
model: ollama-local
status: draft    # 사용자가 편집·확정 후 제거
---

# Weekly Spending Review (DRAFT)

## Steps (detected from pattern)
1. Read Notion expense data for the past week
2. Categorize by tags
3. Compare vs last week
4. Suggest budget adjustments for next week

## Notes for user
This skill was auto-proposed. Edit steps/persona and remove `status: draft` when ready.
```

---

## 5. 구현 노트

### 감지 (주간)
```python
async def detect_repeated_patterns(days: int = 7, min_count: int = 3) -> list[dict]:
    # Hermes 대화 로그 + brain/ 기록에서 패턴 찾기
    # MVP: 간단한 키워드 반복 + 시간 간격 분석
    recent_conversations = await hermes.get_recent_conversations(days=days)
    candidates = cluster_by_topic_similarity(recent_conversations)
    patterns = []
    for cluster in candidates:
        if len(cluster) >= min_count:
            patterns.append({
                "name_suggestion": suggest_name(cluster),
                "frequency": len(cluster),
                "summary": summarize(cluster),
                "sample_flow": extract_common_flow(cluster),
            })
    return patterns
```

### 승격 (승인 후)
```python
async def promote_pattern(pattern: dict, user_approved: bool = True) -> dict:
    if not user_approved:
        await state.mark_pattern_rejected(pattern["name_suggestion"])
        return {"status": "rejected"}

    slug = pattern["name_suggestion"]
    path = f"skills/drafts/{slug}/SKILL.md"
    body = render_skill_template(pattern)
    await file.write(path, body)
    return {"status": "promoted", "path": path}
```

---

## 6. 테스트 포인트

- [ ] 같은 대화 패턴 3회 반복 → 제안 생성
- [ ] 승인 → skills/drafts/ 생성
- [ ] 거절 → 다시 제안 안 됨 (최소 기간)
- [ ] 사용자가 draft 편집 + status 제거 → 정식 skill로
- [ ] MVP는 감지 정확도 낮아도 OK (사용자 승인 필수이므로)

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 오탐 (관련 없는데 제안) | 승인 필수. 거절 패턴 학습. |
| 누락 (진짜 반복되는데 감지 못 함) | 사용자가 수동 DIY (FR-E4)로 대응 |
| 자동 생성 초안 품질 낮음 | status: draft + 사용자 편집 단계 필수 |
| Hermes의 감지와 우리 감지 중복 | Hermes skill_manage 결과를 우리 approval-inbox로 통합 |

---

## 8. 관련 FR

- **FR-E4** DIY (승격 대안)
- **FR-G3** 제안 인박스
- **FR-D3** 저녁 회고
- **FR-D4** 주간 리뷰 (감지 실행 시점)

---

## 9. 구현 단계

- **MVP (Week 4)**: 최소 감지 + 승격 초안 (간단한 키워드 클러스터링)
- **v1.0**: Hermes skill_manage 통합 + 더 정교한 감지
