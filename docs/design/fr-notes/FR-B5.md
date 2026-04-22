# FR-B5: 관련도 정렬

**카테고리**: B. Memory
**우선순위**: 중간 (MVP 포함)

---

## 1. Overview

검색 결과가 단순 시간 역순이 아니라 **관련도 점수** 기준 기본 정렬. 오래된 기록이라도 중요하면 상단.

---

## 2. 관련 컴포넌트

- **Tools**: `memory.search` (sort 파라미터)
- memsearch 내장 RRF (Reciprocal Rank Fusion) 활용

---

## 3. 관련도 계산

memsearch가 내부에서:
1. **Vector similarity** (BGE-M3 코사인)
2. **BM25** (키워드 일치)
3. **RRF (Reciprocal Rank Fusion)**로 통합

추가 가중치 (이 프로젝트 레이어):
- **Recency bump**: 동점일 때 최근 +0.05
- **Entity match bump**: 쿼리에 엔티티 이름 있으면 그 엔티티 연결 기록 +0.1

---

## 4. 정렬 옵션

| sort 값 | 동작 |
|---|---|
| `relevance` (default) | RRF 관련도 + bump |
| `recent` | created_at 내림차순 |
| `oldest` | created_at 오름차순 |
| `score-desc` | 순수 memsearch 점수 내림차순 |

---

## 5. 구현 노트

```python
async def search(..., sort: str = "relevance") -> list[dict]:
    hits = await ms.search(query=query, top_k=top_k * 2)  # 여유 있게
    results = [_normalize(h) for h in hits]

    if sort == "relevance":
        # memsearch 기본 RRF + bump
        for r in results:
            if _has_entity_in_query(query, r["entities"]):
                r["score"] += 0.1
            r["score"] += _recency_bump(r["created_at"])
        results.sort(key=lambda r: r["score"], reverse=True)
    elif sort == "recent":
        results.sort(key=lambda r: r["created_at"], reverse=True)
    elif sort == "oldest":
        results.sort(key=lambda r: r["created_at"])
    elif sort == "score-desc":
        results.sort(key=lambda r: r["score"], reverse=True)

    return results[:top_k]

def _recency_bump(created_at: str) -> float:
    """Last 30 days: +0.05, last 7 days: +0.08."""
    age_days = (datetime.now(ZoneInfo("Asia/Seoul")) - parse_iso(created_at)).days
    if age_days <= 7:
        return 0.08
    if age_days <= 30:
        return 0.05
    return 0.0
```

---

## 6. 테스트 포인트

- [ ] 동일 쿼리, `--sort relevance` vs `--sort recent` 다른 결과
- [ ] 오래된 핵심 기록이 관련도 정렬에서 상단에 오는지 (정성 테스트)
- [ ] `--sort` 미지정 시 relevance 기본
- [ ] 엔티티 쿼리 ("jane") → jane 엔티티 연결 기록 bump 반영

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| bump 계수가 관련도 왜곡 | 설정으로 조정 가능 |
| 사용자가 기대한 순서 아님 | 정렬 옵션 쉽게 전환 |

---

## 8. 관련 FR

- **FR-B1** 기본 검색 (정렬은 B1에 통합)
- **FR-B2** 필터 검색

---

## 9. 구현 단계

- **Week 1 Day 7**: 기본 relevance (memsearch 내장만)
- **Week 2 Day 1**: sort 옵션 + recency bump
- **Week 2 Day 2**: entity bump
