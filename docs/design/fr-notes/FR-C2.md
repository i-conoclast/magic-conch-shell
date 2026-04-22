# FR-C2: 엔티티 승인·거절

**카테고리**: C. Entities
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

초안 엔티티를 **저녁 회고 시간**에 일괄 검토. 승인·거절·수정.

---

## 2. 관련 컴포넌트

- **Skills**: `evening-retro` (통합 포인트)
- **Commands**: `mcs entity confirm {draft}`, `mcs entity reject {draft}`
- **Tools**: `memory.entity_confirm`, `memory.entity_reject`
- **MCP**: tool 노출

---

## 3. 데이터 플로우

```
저녁 22:00 Hermes cron → evening-retro skill
   → approval-inbox에서 entity-draft 항목 조회
   → 각 항목 사용자에게 제시:
     "Jane Smith (people, detected in 1차 면접 후기). Approve?"
   → 사용자 선택:
     승인 → mcs.memory_entity_confirm(draft_path)
            → drafts/ → entities/ 이동
            → frontmatter status 제거
            → approval-inbox에서 제거
     거절 → mcs.memory_entity_reject(draft_path)
            → drafts/ 파일 삭제
            → .brain/rejected-entities.log 기록 (재생성 방지)
     수정 → 사용자가 역할·소속 보완 후 승인
     미루기 → 내일 회고로
```

---

## 4. 사용자 인터랙션 예시

**저녁 회고 대화 (iMessage)**:
```
🌙 저녁 회고. 오늘 확인할 것 3개:

1. 새 인물: Jane Smith (ML Recruiter @ Anthropic)
   첫 언급: [1차 면접 후기]
   [승인] [거절] [수정] [내일]

> 승인

   ✓ people/jane-smith 등록됨.

2. 새 회사: Anthropic
   첫 언급: [1차 면접 후기]
   이미 people/jane-smith가 회사로 연결됨.
   [승인] [거절] [내일]

> 승인

   ✓ companies/anthropic 등록됨.

3. 스킬 승격 제안: "이번 주 지출 회고" 패턴 4회 반복.
   [승인] [거절] [내일]

> 내일
   → 내일 회고로 미룸.

회고 계속할까요? (완료/다음)
```

---

## 5. 구현 노트

### Core
```python
async def entity_confirm(draft_path: str, extra_fields: dict | None = None) -> dict:
    post = frontmatter.loads(await file.read(draft_path))
    meta = post.metadata
    kind = meta["kind"]
    slug = meta["slug"]

    # status 제거, extra_fields 병합
    meta.pop("status", None)
    meta.pop("detected_at", None)
    meta.pop("detection_confidence", None)
    if extra_fields:
        meta.update(extra_fields)

    # drafts → entities 이동
    target = f"brain/entities/{kind}/{slug}.md"
    await file.write(target, frontmatter.dumps(frontmatter.Post(post.content, **meta)))
    await file.delete(draft_path)

    # approval-inbox 제거
    await state.remove_approval_item({"type": "entity-draft", "path": draft_path})

    # back-link 재스캔 (drafts→entities 이동했으므로 기존 참조 업데이트)
    await _rescan_backlinks_for_entity(slug, kind)

    return {"status": "confirmed", "path": target}

async def entity_reject(draft_path: str, reason: str | None = None) -> dict:
    post = frontmatter.loads(await file.read(draft_path))
    meta = post.metadata
    await file.delete(draft_path)
    await state.append_rejected_entity({
        "name": meta["name"],
        "kind": meta["kind"],
        "slug": meta["slug"],
        "reason": reason,
        "rejected_at": now_kst().isoformat(),
    })
    await state.remove_approval_item({"type": "entity-draft", "path": draft_path})
    return {"status": "rejected"}
```

### CLI
```python
@app.command()
def entity_confirm(
    draft: str = typer.Argument(...),
    role: str | None = typer.Option(None),
    company: str | None = typer.Option(None),
) -> None:
    extra = {k: v for k, v in [("role", role), ("company", company)] if v}
    asyncio.run(memory.entity_confirm(draft, extra))
```

---

## 6. 테스트 포인트

- [ ] 초안 승인 → drafts/에서 entities/로 이동, status 제거
- [ ] 초안 거절 → 파일 삭제, rejected-entities.log 기록
- [ ] 승인 중 추가 정보 입력 → 프론트매터 병합
- [ ] 내일로 미룬 항목 다음 회고에 등장
- [ ] 같은 이름 거절 후 다시 감지 → 자동 생성 안 되거나 낮은 priority

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 사용자가 회고 건너뜀 → 초안 쌓임 | 일정 수 초과 시 아침 브리핑에 부드럽게 상기 |
| 거절 후 자동 재생성 루프 | rejected-entities.log 참조해서 감지 skip |
| 실수 거절 | 거절 직후 5분 내 취소 가능 (undo) |

---

## 8. 관련 FR

- **FR-C1** 초안 생성
- **FR-D3** 저녁 회고 (승인 인박스 통합)
- **FR-G3** 제안 인박스
- **FR-C3** back-link (승인 후 재스캔)

---

## 9. 구현 단계

- **Week 3 Day 2**: entity_confirm / reject 함수
- **Week 3 Day 2**: evening-retro skill과 통합
- **Week 3 Day 3**: iMessage 대화형 승인 흐름
