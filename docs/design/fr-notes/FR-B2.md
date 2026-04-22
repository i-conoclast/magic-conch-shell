# FR-B2: 도메인·엔티티 필터 검색

**카테고리**: B. Memory
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

FR-B1 검색에 **도메인·엔티티 필터** 추가. 특정 영역·사람만 관련된 기록 조회.

---

## 2. 관련 컴포넌트

- **Commands**: `mcs search --domain X --entity people/Y`
- **Tools**: `memory.search` (필터 파라미터 추가)
- **MCP**: `memory_search` tool 확장

---

## 3. 데이터 플로우

```
mcs search "follow-up" --domain career --entity people/jane-smith
   → memory.search(query, domain="career", entity="people/jane-smith")
   → memsearch 필터: metadata.domain == "career" AND "people/jane-smith" in metadata.entities
   → 결과 반환
```

---

## 4. 필터 조합

| 필터 | 의미 |
|---|---|
| `--domain X` | 해당 도메인 기록만 |
| `--entity X` | 본문·프론트매터에서 해당 엔티티 연결된 기록만 |
| `--domain X --entity Y` | 교집합 (X 도메인 AND Y 엔티티) |
| `--type note/signal/daily` | 타입 필터 |
| `--kr 1.2` | **KR 관련 기록만** (frontmatter `kr_ref == "1.2"`) |
| 필터 + 쿼리 | 필터 안에서 쿼리 관련도 정렬 |

---

## 5. 예시

```bash
# 재무 도메인 중 "리밸런싱" 관련
mcs search "리밸런싱" --domain finance

# Jane 관련만
mcs search --entity people/jane-smith  # 쿼리 없어도 OK → Jane 연결 모든 것

# Jane + 면접
mcs search "면접" --entity people/jane-smith

# Anthropic 회사 관련 중 최근 순
mcs search --entity companies/anthropic --sort recent

# KR 1.2 (영문 블로그)에 연결된 모든 기록
mcs search --kr 1.2

# KR 1.2에 연결된 기록 중 "draft" 키워드
mcs search "draft" --kr 1.2

# KR 5.3 (재무) 관련 최근 순
mcs search --kr 5.3 --sort recent
```

---

## 6. 구현 노트

```python
async def search(
    query: str | None = None,
    domain: str | None = None,
    entity: str | None = None,
    type: str | None = None,
    kr: str | None = None,
    top_k: int = 10,
    sort: str = "relevance",
) -> list[dict]:
    ms = _get_memsearch()
    filters = {}
    if domain:
        filters["metadata.domain"] = domain
    if entity:
        filters["metadata.entities"] = {"$in": [entity]}
    if type:
        filters["metadata.type"] = type
    if kr:
        # kr 필터: frontmatter.kr_ref 에 값이 있는 기록만
        filters["metadata.kr_ref"] = kr

    if query:
        hits = await ms.search(query=query, top_k=top_k, filters=filters)
    else:
        # 쿼리 없으면 시간 역순 반환
        hits = await ms.list_by_metadata(filters=filters, top_k=top_k, sort="created_at:desc")

    return [_normalize(h) for h in hits]
```

### KR 유효성 검증 (옵션)

사용자가 존재하지 않는 KR 지정 시 plan-tracker MCP로 확인:
```python
async def validate_kr(kr: str) -> bool:
    krs = await okr.kr_list()
    if krs is None:
        return True  # plan-tracker down → 그냥 진행
    return any(k["id"] == kr for k in krs)
```

---

## 7. 테스트 포인트

- [ ] 도메인 필터만 → 해당 도메인만 반환
- [ ] 엔티티 필터만, 쿼리 없음 → 그 엔티티 연결된 모든 기록
- [ ] 도메인+엔티티 교집합
- [ ] 잘못된 도메인 이름 → 에러 + 제안
- [ ] 존재하지 않는 엔티티 → 빈 결과 + 안내
- [ ] **`--kr 1.2` → kr_ref 필드가 "1.2"인 기록만 반환**
- [ ] **쿼리 없이 `--kr 1.2` → 해당 KR 관련 모든 기록 시간 역순**
- [ ] **잘못된 KR id (존재 X) → plan-tracker에서 검증 가능 시 안내, 불가 시 빈 결과**

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| memsearch 필터 성능 | Milvus Lite는 메타 필터 지원. 필요 시 pre-filter. |
| 엔티티 slug 오타 | 검색 전 엔티티 존재 확인 + 퍼지 매칭 제안 |

---

## 9. 관련 FR

- **FR-B1** 기본 검색
- **FR-B4** 엔티티 타임라인 (엔티티 필터의 시간순 변종)
- **FR-C3** back-link (엔티티 연결)

---

## 10. 구현 단계

- **Week 1 Day 5**: 필터 파라미터 CLI 추가
- **Week 1 Day 6**: memsearch 메타 필터 통합
