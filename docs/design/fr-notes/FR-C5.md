# FR-C5: 동명이인·중복 처리

**카테고리**: C. Entities
**우선순위**: 중간 (MVP 포함)

---

## 1. Overview

같은 이름 엔티티가 서로 다른 인물·회사일 수 있음. 구분·병합·분리 지원.

**원칙**: 자동 병합 **없음**. 사용자 명시 동작만.

---

## 2. 관련 컴포넌트

- **Commands**: `mcs entity merge {from} {to}`, `mcs entity split {slug}`
- **Tools**: `memory.entity_merge`, `memory.entity_split`
- **MCP**: tool 노출

---

## 3. 동명이인 감지 → 행동

**신규 감지 시** (FR-C1이 호출):
1. 이름으로 검색
2. 기존 엔티티 존재하면:
   - **자동 병합 X**
   - 신규 초안 생성 (suffix `-2`, `-3`)
   - 승인 인박스에 "기존 {slug}와 같은 인물인가요?" 제안

예:
```
brain/entities/people/kim.md          (기존)
brain/entities/drafts/people/kim-2.md (신규 초안)
```

저녁 회고:
```
새 draft: kim-2
  기존 Kim과 같은 인물입니까?
  [같음 — 병합] [다름 — 별개 유지] [내일]
```

---

## 4. Merge 동작

```python
async def entity_merge(from_slug: str, to_slug: str) -> dict:
    """from → to로 병합."""
    from_path = _entity_path_from_slug(from_slug)
    to_path = _entity_path_from_slug(to_slug)

    if not await file.exists(from_path) or not await file.exists(to_path):
        raise EntityNotFound(...)

    from_post = frontmatter.loads(await file.read(from_path))
    to_post = frontmatter.loads(await file.read(to_path))

    # 1. to의 프론트매터 보강 (from에 있지만 to에 없는 필드)
    for k, v in from_post.metadata.items():
        if k not in to_post.metadata and v:
            to_post.metadata[k] = v

    # 2. 본문 섹션 병합 (Context, Recent, Manual notes 등)
    merged_body = _merge_bodies(from_post.content, to_post.content)
    to_post.content = merged_body

    # 3. to에 저장
    await file.write(to_path, frontmatter.dumps(to_post))

    # 4. from을 참조하던 모든 기록을 to로 재타겟
    refs = await memory.find_all_records_referencing(from_slug)
    for record in refs:
        r_post = frontmatter.loads(await file.read(record))
        r_post.metadata["entities"] = [to_slug if e == from_slug else e for e in r_post.metadata.get("entities", [])]
        await file.write(record, frontmatter.dumps(r_post))

    # 5. from 파일 삭제 + undo 이력
    await state.append_merge_history({
        "from": from_slug,
        "to": to_slug,
        "from_path": from_path,
        "from_content_backup": await file.read(from_path),
        "affected_records": refs,
        "merged_at": now_kst().isoformat(),
    })
    await file.delete(from_path)

    # 6. back-link 재빌드 (FR-C3)
    await memory.rebuild_backlinks()

    return {"status": "merged", "to": to_slug, "affected_records": len(refs)}
```

---

## 5. Split (병합 되돌리기) — MVP 최소

```python
async def entity_split_undo(merge_id: str) -> dict:
    """가장 최근 merge 되돌리기."""
    entry = await state.pop_merge_history()  # 또는 id로 특정
    # from_path 복원 + affected_records의 entities 원복
    ...
```

**MVP는 undo만 지원**. 일반적 split(한 엔티티를 둘로 쪼개기)은 v1.0.

---

## 6. CLI

```bash
# 병합
mcs entity merge people/kim people/kim-jihye
# → kim의 모든 참조를 kim-jihye로 재타겟, kim 파일 삭제

# 되돌리기
mcs entity merge --undo

# 병합 이력
mcs entity merge-history
```

---

## 7. 테스트 포인트

- [ ] 병합 후 from 엔티티 없어짐, to에 모든 참조 집약
- [ ] 병합 후 `mcs entity show to_slug` → 프론트매터·본문 통합 확인
- [ ] 병합 후 back-link 갱신
- [ ] undo → 원상복구 (affected records도 원래 slug로)
- [ ] 잘못된 slug → 에러
- [ ] 자기 자신과 병합 시도 → 에러

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 잘못된 병합 (실수로 다른 인물 합침) | undo 지원. merge-history로 추적 |
| 복잡한 본문 병합 시 정보 손실 | 전체 백업 state에 저장. undo 시 정확히 복원. |
| 참조 업데이트 중 실패 → 부분 병합 | 트랜잭션적으로: 임시 파일로 준비 후 원자 이동. 실패 시 전체 롤백. |
| 동명이인이 너무 많아 혼란 | suffix 규칙 + 승인 인박스에 식별 정보 제시 |

---

## 9. 관련 FR

- **FR-C1** 초안 (동명 감지 시점)
- **FR-C3** back-link (병합 후 재빌드)
- **FR-C4** 프로필 (본문 병합)
- **FR-D3** 저녁 회고 (병합 제안)

---

## 10. 구현 단계

- **Week 3 Day 3**: merge 함수 + undo state
- **Week 3 Day 4**: CLI 커맨드
- **v1.0**: 일반 split 지원
