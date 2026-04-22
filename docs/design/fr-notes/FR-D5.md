# FR-D5: 확정 플랜의 외부 시스템 반영

**카테고리**: D. Planning
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

사용자가 대화로 확정한 플랜을 **Notion Daily Tasks DB**에 자동 생성. 중복 방지·실패 시 로컬 큐.

---

## 2. 관련 컴포넌트

- **Skills**: `plan-confirm`의 일부
- **Tools**: `notion.create_page`, `memory.save_plan`
- **State**: `.brain/pending-push.jsonl`
- **의존**: FR-H1 (Notion 쓰기 계약)

---

## 3. 데이터 플로우

```
plan-confirm에서 사용자 확정
   → 각 플랜 항목마다:
     1. brain/plans/YYYY-MM-DD-{slug}.md 저장 (이력)
     2. notion.create_page(Daily Tasks DB, properties={
          Title, Date, Domain, KR (선택), 우선순위, Source="magic-conch", ...
        })
     3. 성공: notion_page_id 기록
     4. 실패: .brain/pending-push.jsonl에 추가, 재시도 예약
   → 사용자에게 "N건 반영 완료 / M건 큐잉" 알림
```

---

## 4. 저장 파일 예시

`brain/plans/2026-04-19-jane-followup-email.md`:
```markdown
---
id: 2026-04-19-jane-followup-email
type: plan
domain: career
entities: [people/jane-smith, jobs/anthropic-mle]
confirmed_at: 2026-04-19T07:23:11+09:00
notion_page_id: xxx-xxx-xxx
priority: high
due: 2026-04-25
kr_ref: 1.4
---

Jane에게 follow-up 메일 보내기.
- 1차 면접 감사
- LoRA 코드 저장소 링크
- 2차 일정 확인
```

---

## 5. Notion 필드 매핑

[requirements/03-functional/H-integration-criteria.md](../../requirements/03-functional/H-integration-criteria.md) 참조.

필수 필드: Title, Date, Domain(영역), 세부활동, 계획상태=Planned, Source="magic-conch"
선택: KR (Relation→DB2), 우선순위, Brain Ref (URL), Confirmed At

---

## 6. 구현 노트

```python
async def save_and_push_plan(plan: PlanItem) -> dict:
    # 1. brain/plans에 저장
    slug = f"{plan.date}-{slugify(plan.title)}"
    path = f"brain/plans/{slug}.md"
    frontmatter = {
        "id": slug,
        "type": "plan",
        "domain": plan.domain,
        "entities": plan.entities,
        "confirmed_at": now_kst().isoformat(),
        "priority": plan.priority,
        "due": plan.due,
        "kr_ref": plan.kr_ref,
    }
    await file.write(path, assemble(frontmatter, plan.body))

    # 2. Notion push
    try:
        page_id = await notion.create_page(
            db_id=config.NOTION_DAILY_TASKS_DB,
            properties=_to_notion_properties(plan, brain_ref=path),
        )
        # notion_page_id 기록
        frontmatter["notion_page_id"] = page_id
        await file.update_frontmatter(path, frontmatter)
        return {"status": "pushed", "page_id": page_id}
    except NotionError as e:
        # 로컬 큐
        await state.append_push_queue({
            "op": "create",
            "db": "daily_tasks",
            "payload": _to_notion_properties(plan, brain_ref=path),
            "brain_ref": path,
            "retries": 0,
            "last_error": str(e),
            "created_at": now_kst().isoformat(),
        })
        return {"status": "queued", "error": str(e)}
```

---

## 7. 재시도 전략

`.brain/pending-push.jsonl`의 항목들을:
- autopilot 주기 (5분)마다 재시도
- 지수적 backoff: 5s → 10s → 30s → 2m → 10m → 30m → 1h (상한)
- 5회 실패 시 failed 플래그 + 사용자 알림

---

## 8. 테스트 포인트

- [ ] 단일 플랜 확정 → Notion에 1건 생성
- [ ] 3건 확정 → Notion에 3건 생성
- [ ] Notion 다운 중 확정 → 큐잉, "N건 큐" 알림
- [ ] Notion 복구 → 자동 재시도로 반영
- [ ] 이미 반영된 plan 재확정 시도 → 중복 방지
- [ ] brain/plans/ 파일에 notion_page_id 기록됨

---

## 9. 리스크·완화

| 리스크 | 완화 |
|---|---|
| Notion API rate limit | 배치 + 지수적 backoff |
| 계획 필드 스키마 변경 | plan-tracker contract 버전 체크 |
| 로컬 큐 파일 손상 | 매 append마다 append-only, 손상 시 새로 시작 |
| 중복 반영 | brain/plans의 notion_page_id 존재 여부로 체크 |

---

## 10. 관련 FR

- **FR-D2** 플랜 확정 (이 FR의 발동 지점)
- **FR-H1** Notion 쓰기 (계약)
- **FR-I3** 장애 대응 (큐·재시도)

---

## 11. 구현 단계

- **Week 3 Day 3**: save_and_push_plan 기본
- **Week 3 Day 4**: 로컬 큐 + 재시도
- **Week 4 Day 2**: autopilot에 재시도 루프 통합
