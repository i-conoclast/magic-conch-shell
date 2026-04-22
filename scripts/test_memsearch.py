"""Day 2 — memsearch + BGE-M3 한국어 검색 품질 검증."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from memsearch import MemSearch


REPO_ROOT = Path(__file__).resolve().parents[1]
BRAIN_DIR = REPO_ROOT / "brain"
MILVUS_DB = REPO_ROOT / ".brain" / "memsearch.db"


async def build_index() -> MemSearch:
    print(f"\n─── 인덱싱 시작 ({BRAIN_DIR}) ───")
    t0 = time.time()
    ms = MemSearch(
        paths=[str(BRAIN_DIR)],
        embedding_provider="ollama",
        embedding_model="bge-m3",
        embedding_base_url="http://localhost:11434",
        milvus_uri=str(MILVUS_DB),
    )
    await ms.index()
    print(f"인덱싱 완료: {time.time() - t0:.1f}s")
    return ms


async def run_query(ms: MemSearch, query: str, top_k: int = 3) -> None:
    t0 = time.time()
    results = await ms.search(query, top_k=top_k)
    dt = time.time() - t0
    print(f"\n🔍 {query!r}  ({dt * 1000:.0f}ms, {len(results)} 결과)")
    for i, r in enumerate(results, 1):
        # r is Chunk/dict — print all available fields safely
        if hasattr(r, "__dict__"):
            fields = vars(r)
        elif hasattr(r, "get"):
            fields = dict(r)
        else:
            fields = {"repr": repr(r)}
        path = fields.get("path") or fields.get("file_path") or fields.get("source") or "?"
        score = fields.get("score") or fields.get("distance") or "?"
        text = fields.get("text") or fields.get("content") or ""
        excerpt = (str(text) or "").replace("\n", " ")[:100]
        fname = Path(str(path)).name
        score_s = f"{score:.3f}" if isinstance(score, float) else str(score)
        print(f"  [{i}] {score_s:>8}  {fname}")
        if excerpt:
            print(f"        ↳ {excerpt}")


async def main() -> None:
    ms = await build_index()

    queries = [
        "Anthropic 면접",
        "LoRA 구현",
        "주간 운동",
        "파트너와 시간",
        "비상금 재무",
        "수면 부족",
        "포트폴리오 피드백",
        "RAG 품질 측정",
        "독서 노트",
        "아이디어 메모",
    ]

    print("\n═══ 10개 쿼리 실측 ═══")
    for q in queries:
        await run_query(ms, q, top_k=3)

    print("\n───────── 검증 완료 ─────────")


if __name__ == "__main__":
    asyncio.run(main())
