# FR-C3: 자동 양방향 연결 (back-link)

**카테고리**: C. Entities
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

기록 ↔ 엔티티 간 **양방향 참조** 자동 생성·유지. 기록에서 엔티티로, 엔티티에서 기록으로 따라갈 수 있음.

---

## 2. 관련 컴포넌트

- **Tools**: `memory.rebuild_backlinks`, `memory.add_backlink`, `memory.remove_backlink`
- **Skills**: 저장 이벤트마다 자동 발동
- **MCP**: tool 노출

---

## 3. 데이터 플로우

```
기록 저장 시
   → 프론트매터 entities: [people/jane-smith] 있으면:
       각 엔티티에 대해 add_backlink(entity, record)
   → 본문에서 엔티티 이름 언급 감지 (FR-G2)
       추가 연결 + add_backlink
   → 엔티티 프로필의 "Back-links (auto)" 섹션 갱신

엔티티 삭제 시
   → 해당 엔티티 참조하던 모든 기록에서 제거
   → 각 기록 프론트매터 entities 배열에서 slug 제거

엔티티 병합 시 (FR-C5)
   → from 엔티티의 모든 back-link을 to 엔티티로 재타겟
```

---

## 4. Entity 프로필의 back-link 섹션

```markdown
## Back-links (auto)
<!-- AUTO-GENERATED BELOW. DO NOT EDIT. -->
- [[domains/career/2026-04-19-anthropic-mle-1st-round]] (2026-04-19, note)
- [[domains/career/2026-04-10-jane-feedback]] (2026-04-10, note)
- [[signals/2026-03-28-142230]] (2026-03-28, signal)
<!-- END AUTO-GENERATED -->
```

**주석으로 구분**: 자동 영역과 사용자 수동 영역(Manual notes 등)이 섞이지 않음.

---

## 5. 구현 노트

### 증분 갱신
```python
async def add_backlink(entity_slug: str, record_path: str):
    entity_path = _entity_path_from_slug(entity_slug)  # brain/entities/people/jane-smith.md
    content = await file.read(entity_path)

    # AUTO 섹션 파싱
    section = _extract_auto_section(content)
    record_meta = await memory.get_record_metadata(record_path)
    new_line = f"- [[{record_path.removeprefix('brain/').removesuffix('.md')}]] ({record_meta['created_at'][:10]}, {record_meta['type']})"

    if new_line in section:
        return  # 이미 있음

    # 시간 역순 정렬 유지
    lines = section.strip().split("\n") + [new_line]
    lines.sort(key=_extract_date_from_line, reverse=True)

    # 섹션 교체
    new_content = _replace_auto_section(content, "\n".join(lines))
    await file.write(entity_path, new_content)

_AUTO_START = "<!-- AUTO-GENERATED BELOW. DO NOT EDIT. -->"
_AUTO_END = "<!-- END AUTO-GENERATED -->"

def _extract_auto_section(content: str) -> str:
    start = content.find(_AUTO_START)
    end = content.find(_AUTO_END)
    if start == -1 or end == -1:
        return ""
    return content[start + len(_AUTO_START):end]
```

### 전체 재빌드
```python
async def rebuild_backlinks():
    """
    All-from-scratch rescan. Used in `mcs reindex --backlinks`.
    """
    # 모든 엔티티의 auto 섹션 비우기
    for entity_path in await file.list_all("brain/entities/"):
        if "/drafts/" in entity_path:
            continue
        content = await file.read(entity_path)
        cleared = _replace_auto_section(content, "")
        await file.write(entity_path, cleared)

    # 모든 기록 스캔
    for record_path in await file.list_all("brain/"):
        if "/entities/" in record_path or "/session-state/" in record_path:
            continue
        meta = await memory.get_record_metadata(record_path)
        entities = meta.get("entities", [])
        for slug in entities:
            await add_backlink(slug, record_path)
```

---

## 6. 테스트 포인트

- [ ] 새 기록 저장 → 지정된 엔티티 프로필에 back-link 등장
- [ ] 기록 수정 → entities 변경 시 back-link 갱신 (추가·제거)
- [ ] 엔티티 삭제 → 관련 기록의 entities에서 제거
- [ ] 엔티티 병합 (FR-C5) → 통합 엔티티로 재타겟
- [ ] `mcs reindex --backlinks` → 전체 재빌드 정상
- [ ] 수동 편집 영역은 건드리지 않음 (주석 경계 유지)

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 수동 영역 침범 | 주석 경계 + 파싱 검증 |
| 재빌드 오래 걸림 (기록 많을 때) | 증분 갱신 위주, 전체는 수동 트리거만 |
| 순환 참조 (사람 A가 회사 X에 있고, X의 소개가 A) | 단방향 link만. 프로필에만 자동 삽입. |
| 파일 동시 편집 충돌 | 파일 락 또는 큐 처리 |

---

## 8. 관련 FR

- **FR-C1·C2** 엔티티 라이프사이클
- **FR-B4** 엔티티 타임라인 (이 back-link의 주된 사용처)
- **FR-G2** 자동 태깅 (연결 생성 주 경로)
- **FR-I2** 인덱스 재빌드 (backlinks 재스캔 포함)

---

## 9. 구현 단계

- **Week 2 Day 5**: add/remove backlink 함수
- **Week 3 Day 1**: 기록 저장 이벤트 훅 연결
- **Week 4 Day 2**: `mcs reindex --backlinks` 구현
