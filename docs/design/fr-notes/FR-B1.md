# FR-B1: 자유 질의 검색

**카테고리**: B. Memory
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

사용자가 자연어 한 줄 질의를 던지면 **의미상·키워드상 관련 있는 기록**이 관련도 순서로 반환. memsearch의 하이브리드 검색 활용.

---

## 2. 관련 컴포넌트

- **Commands**: `/search "..."`, `mcs search "..."`
- **Tools**: `memory.search` (memsearch 래퍼)
- **MCP**: `memory_search` tool
- **Skills**: 없음 (도구 수준)
- **라이브러리**: memsearch + Milvus Lite + BGE-M3 임베딩

---

## 3. 데이터 플로우

```
사용자: mcs search "지난 달 anthropic 관련"
   → tools.memory.search(query="지난 달 anthropic 관련", top_k=10)
   → memsearch 하이브리드 검색
     - vector search (BGE-M3 임베딩)
     - BM25 키워드 검색
     - RRF reranking
   → 결과 리스트 (경로·발췌·score·meta)
   → CLI: rich table 출력
   → MCP: list[dict] 반환
```

---

## 4. 입력·출력

### 입력
```python
query: str                       # 자유 텍스트
top_k: int = 10                  # 최대 결과 수
sort: str = "relevance"          # "relevance" | "recent" | "oldest"
kr: str | None = None            # KR id 필터 (예: "1.2") — plan-tracker MCP 경유
```

### 출력 (각 결과)
```python
{
    "path": "brain/domains/career/2026-04-10-jane-feedback.md",
    "id": "2026-04-10-jane-feedback",
    "score": 0.87,
    "excerpt": "Jane한테 받은 피드백. ML 방향 유지 + ...",
    "domain": "career",
    "entities": ["people/jane-smith", "companies/anthropic"],
    "created_at": "2026-04-10T...",
    "type": "note",
}
```

---

## 5. CLI 표시 예시

```
$ mcs search "지난 달 anthropic"
┌─────┬────────────┬──────────┬────────────────────────────────────┐
│ #   │ Date       │ Domain   │ Excerpt                            │
├─────┼────────────┼──────────┼────────────────────────────────────┤
│ 1   │ 2026-04-10 │ career   │ Jane한테 받은 피드백. ML 방향...   │
│ 2   │ 2026-03-28 │ career   │ 리쿠르터 콜. 1차 기술 인터뷰...    │
│ 3   │ 2026-03-12 │ career   │ 첫 접촉. Anthropic MLE 관심...     │
└─────┴────────────┴──────────┴────────────────────────────────────┘
3 results in 0.8s
```

---

## 6. 구현 노트

### memsearch 래퍼
```python
# tools/memory.py
from memsearch import MemSearch

_ms: MemSearch | None = None

def _get_memsearch() -> MemSearch:
    global _ms
    if _ms is None:
        _ms = MemSearch(
            db_path=".brain/memsearch-db",
            embed_model="bge-m3",
            embed_endpoint="http://localhost:11434",  # Ollama
        )
    return _ms

async def search(
    query: str,
    domain: str | None = None,
    entity: str | None = None,
    top_k: int = 10,
    sort: str = "relevance",
) -> list[dict]:
    ms = _get_memsearch()
    hits = await ms.search(
        query=query,
        top_k=top_k,
        filters={
            "domain": domain,
            "entities": [entity] if entity else None,
        }
    )
    results = [_normalize(h) for h in hits]
    if sort == "recent":
        results.sort(key=lambda r: r["created_at"], reverse=True)
    elif sort == "oldest":
        results.sort(key=lambda r: r["created_at"])
    return results

def _normalize(hit) -> dict:
    return {
        "path": hit.path,
        "id": hit.metadata.get("id"),
        "score": hit.score,
        "excerpt": hit.snippet(max_len=120),
        "domain": hit.metadata.get("domain"),
        "entities": hit.metadata.get("entities", []),
        "created_at": hit.metadata.get("created_at"),
        "type": hit.metadata.get("type"),
    }
```

### CLI
```python
# src/mcs/commands/search.py
import typer
from rich.table import Table
from rich.console import Console

app = typer.Typer()

@app.command()
def search(
    query: str = typer.Argument(...),
    top_k: int = typer.Option(10, "--top-k", "-k"),
    sort: str = typer.Option("relevance", "--sort"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    results = asyncio.run(memory.search(query, top_k=top_k, sort=sort))
    if as_json:
        typer.echo(json.dumps(results, ensure_ascii=False, indent=2))
        return
    table = Table("#", "Date", "Domain", "Excerpt")
    for i, r in enumerate(results, 1):
        table.add_row(str(i), r["created_at"][:10], r["domain"] or "-", r["excerpt"])
    Console().print(table)
```

### MCP
```python
# mcp/mcs-server.py
@mcp.tool()
async def memory_search(query: str, top_k: int = 10) -> list[dict]:
    """Search brain/ with hybrid vector + BM25 + RRF."""
    return await memory.search(query, top_k=top_k)
```

---

## 7. 테스트 포인트

- [ ] 한국어 질의 → 관련 한국어 기록 반환
- [ ] 영어 질의 → 관련 영어·한국어 기록 모두 반환 (다국어 임베딩)
- [ ] 완전 일치하는 단어 없어도 의미 유사 기록 반환
- [ ] 질의 결과 2초 이내 (NFR-02)
- [ ] 빈 결과 시 "해당 없음" 메시지
- [ ] 1000건 이상 인덱싱된 상태에서도 응답 시간 유지
- [ ] memsearch 다운 시 grep fallback 동작 (FR-I3 연계)

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| BGE-M3가 한국어 품질 낮음 | Week 1 검증 필수. 대안: `multilingual-e5-large`, `ko-sbert` |
| memsearch 인덱스 손상 | `mcs reindex`로 재빌드 (FR-I2) |
| Ollama(임베딩 서버) 다운 | memsearch가 다른 모델로 fallback 또는 검색 일시 비활성 |
| 대량 결과 반환으로 터미널 오버플로 | top_k 기본 10, 필요 시 `--top-k 50` |
| 관련도 정렬이 기대와 다름 | `--sort recent`로 시간순 전환 (FR-B5) |

---

## 9. 관련 FR

- **FR-B2** 도메인·엔티티 필터 (검색 확장)
- **FR-B5** 관련도 정렬 (정렬 로직)
- **FR-I2** 인덱스 재빌드
- **FR-I3** 장애 대응 (memsearch fallback)
- **FR-G1** 세션 로그도 검색 대상 (저장된 것은 모두 인덱스)

---

## 10. 구현 단계

- **Week 1 Day 4**: memsearch 설치·초기 인덱싱
- **Week 1 Day 5**: `mcs search` 기본 CLI
- **Week 1 Day 6**: Rich table 출력 + `--sort`·`--json` 옵션
- **Week 2 Day 1**: MCP tool 노출
