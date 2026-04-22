# FR-B4: 엔티티 타임라인 뷰

**카테고리**: B. Memory
**우선순위**: 높음 (MVP 필수 — Step 3 핵심 보기 단위)

---

## 1. Overview

특정 엔티티(사람·회사·직무 등)를 기준으로 **관련 모든 기록이 시간 역순**으로 나열. "지난 달 Jane 관련된 모든 것" 같은 쿼리.

---

## 2. 관련 컴포넌트

- **Commands**: `mcs entity timeline people/jane-smith [--since]`
- **Tools**: `memory.entity_timeline`
- **MCP**: `memory_entity_timeline`
- **의존**: FR-C3 back-link (엔티티-노트 연결)

---

## 3. 데이터 플로우

```
mcs entity timeline people/jane-smith --since "지난달"
   → memory.entity_timeline(slug, since=...)
     1. 엔티티 존재 확인
     2. 엔티티 프로필 (Section 4.2 로드)
     3. back-link 목록 가져오기 (프로필의 auto 섹션 or memsearch 필터)
     4. 기간 필터 (since / until)
     5. 시간 역순 정렬
   → 엔티티 헤더 + 기록 리스트 표시
```

---

## 4. 출력 예시

```
👤 Jane Smith
   Role: ML Recruiter @ Anthropic
   Relation: professional
   First met: 2026-03-12
   Last contact: 2026-04-10
   Next follow-up: 2026-04-25

🎯 Related KRs (user-declared)
   - KR 1.4 지원 40건 (5 related records)
   - KR 1.5 Mock interview 8회 (1 related record)

📝 Timeline (since 지난달) — 6 records
   2026-04-10  career   [KR 1.4]   "Jane한테 받은 피드백..."
   2026-04-08  career   [KR 1.4]   "2차 면접 일정 조율 중..."
   2026-03-28  career   [KR 1.4]   "리쿠르터 콜 끝. ML 방향..."
   2026-03-15  general              "Jane 추천 읽을거 3개..."
   2026-03-12  career   [KR 1.4]   "첫 접촉. Anthropic MLE..."

   (by type: 면접 후기 2, 자유 메모 4)

[Open entity profile: brain/entities/people/jane-smith.md]
```

**🎯 Related KRs 섹션은 명시 선언된 경우만** 등장.

---

## 5. 엔티티 프로필의 related_krs (명시적 선언)

**원칙**: 자동 추론 금지. 사용자가 엔티티 프론트매터에 **직접 선언**한 KR만 표시.

`brain/entities/people/jane-smith.md`:
```yaml
---
kind: people
slug: jane-smith
name: Jane Smith
role: ML Recruiter
company: companies/anthropic
related_krs: [1.4, 1.5]          # 사용자 명시 선언 (optional)
---
```

이유:
- 자동 추론은 noise 많음 (book 엔티티에 억지 KR 등)
- 사용자가 의도한 연결만 표시
- 명확성 우선

**자동 집계는?** — 프로필에 `related_krs: [1.4]`이 있을 때만:
- "5 related records" 카운트는 frontmatter `entities: [people/jane-smith]` AND `kr_ref: 1.4`인 기록 수

## 6. 구현 노트

```python
async def entity_timeline(
    slug: str,
    since: str | None = None,
    until: str | None = None,
    type_filter: str | None = None,
) -> dict:
    # 1. 엔티티 프로필 로드
    profile = await memory.entity_get(slug)
    if not profile:
        raise EntityNotFound(slug)

    # 2. 관련 기록 조회
    since_date = parse_date(since) if since else None
    until_date = parse_date(until) if until else None

    records = await memory.search(
        query=None,
        entity=slug,
        sort="recent",
        top_k=1000,  # 타임라인은 많이
    )

    # 3. 기간 필터
    if since_date or until_date:
        records = [r for r in records if _in_range(r["created_at"], since_date, until_date)]

    # 4. 타입 필터
    if type_filter:
        records = [r for r in records if r["type"] == type_filter]

    # 5. 타입별 카운트
    by_type = Counter(r["type"] for r in records)

    # 6. Related KRs (명시 선언만)
    related_krs = profile["frontmatter"].get("related_krs", [])
    kr_info = []
    if related_krs:
        # KR 메타 정보 (제목 등) plan-tracker MCP에서
        all_krs = await okr.kr_list() or []
        kr_dict = {k["id"]: k for k in all_krs}
        for kr_id in related_krs:
            if kr_id in kr_dict:
                count = sum(1 for r in records if r.get("kr_ref") == kr_id)
                kr_info.append({
                    "id": kr_id,
                    "title": kr_dict[kr_id]["title"],
                    "related_record_count": count,
                })

    return {
        "entity": profile,
        "related_krs": kr_info,
        "records": records,
        "count": len(records),
        "by_type": dict(by_type),
    }
```

---

## 6. 테스트 포인트

- [ ] 활성 엔티티 타임라인 → 모든 관련 기록 시간 역순
- [ ] 기간 필터 `--since "지난 달"`
- [ ] 기록 0건 엔티티 → 프로필만 표시 + 안내
- [ ] 존재하지 않는 slug → 에러 + 유사 제안
- [ ] 본문 언급만 된 기록 (frontmatter entities에는 없지만 본문에 이름) — 포함 여부 옵션
- [ ] **`related_krs: [1.4]` 프로필 → 🎯 Related KRs 섹션 표시**
- [ ] **`related_krs` 없는 프로필 → KR 섹션 출력 안 함** (자동 추론 X)
- [ ] **타임라인 레코드의 `kr_ref`도 함께 표시** (라벨 `[KR 1.4]`)
- [ ] plan-tracker MCP down 시 KR 제목 없이 id만 표시 (graceful)

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| back-link이 최신 아닐 때 | `mcs reindex --backlinks`로 강제 재스캔 |
| 본문 언급만으로는 모호 (동명이인) | 명시적 `entities:` 프론트매터 신뢰 우선 |
| 1000+ 기록 시 느림 | 페이징 옵션 |

---

## 8. 관련 FR

- **FR-C3** back-link 자동 생성 (이 타임라인의 기반)
- **FR-C4** 프로필 조회
- **FR-B2** 필터 검색 (엔티티 필터와 공유 로직)
- **FR-C5** 동명이인 (타임라인 분리 이슈)

---

## 9. 구현 단계

- **Week 2 Day 4**: entity_timeline 핵심 로직
- **Week 2 Day 5**: 기간·타입 필터 + Rich 출력
- **Week 3 Day 1**: MCP tool 노출
