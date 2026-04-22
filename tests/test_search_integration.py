"""Integration test: capture → index → search roundtrip.

Skipped automatically when Ollama is unreachable on localhost:11434.
Embedding is real and takes ~200ms per memo, so we keep the count low.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from mcs.adapters import search as search_mod
from mcs.adapters.memory import capture
from mcs.adapters.search import search, sync_file


def _ollama_reachable() -> bool:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
    except Exception:
        return False
    if r.status_code != 200:
        return False
    body = r.json()
    models = {m.get("name", "") for m in body.get("models", [])}
    return any(name.startswith("bge-m3") for name in models)


ollama_required = pytest.mark.skipif(
    not _ollama_reachable(),
    reason="Ollama with bge-m3 not reachable on localhost:11434",
)


@pytest.fixture
def fresh_engine():
    """Force a new MemSearch engine per test (module-global singleton)."""
    search_mod._engine = None
    search_mod._indexed_once = False
    yield
    # Best-effort teardown — close the Milvus connection so the tmp dir
    # can be cleaned up without Windows-style file locks on pytest exit.
    if search_mod._engine is not None:
        try:
            search_mod._engine.close()
        except Exception:
            pass
    search_mod._engine = None
    search_mod._indexed_once = False


@ollama_required
@pytest.mark.asyncio
async def test_capture_then_search_finds_memo(
    tmp_brain: Path,
    fresh_engine: None,
) -> None:
    result = capture(
        text="LoRA fine-tuning 메모 for roundtrip test",
        domain="ml",
    )
    await sync_file(result.path)

    hits = await search("LoRA fine-tuning", limit=3, auto_index=False)

    assert hits, "expected at least one hit after indexing"
    assert hits[0].path == result.path.resolve()
    assert hits[0].type == "note"
    assert hits[0].domain == "ml"


@ollama_required
@pytest.mark.asyncio
async def test_search_domain_filter_restricts_results(
    tmp_brain: Path,
    fresh_engine: None,
) -> None:
    career_note = capture(text="면접 준비 자료 정리", domain="career")
    ml_note = capture(text="면접용 ML 알고리즘 복습", domain="ml")
    await sync_file(career_note.path)
    await sync_file(ml_note.path)

    hits = await search("면접", domain="career", limit=5, auto_index=False)

    assert hits, "expected at least one career hit"
    for h in hits:
        assert h.domain == "career"
        assert "domains/career" in h.rel_path.replace("\\", "/")


@ollama_required
@pytest.mark.asyncio
async def test_search_entity_filter_drops_non_matching(
    tmp_brain: Path,
    fresh_engine: None,
) -> None:
    with_jane = capture(
        text="Jane과 Anthropic 인터뷰 후속",
        domain="career",
        entities=["people/jane-smith"],
    )
    without_jane = capture(
        text="일반 커리어 메모, Jane 관련 아님",
        domain="career",
    )
    await sync_file(with_jane.path)
    await sync_file(without_jane.path)

    hits = await search(
        "Jane 인터뷰",
        entity="people/jane-smith",
        limit=5,
        auto_index=False,
    )

    assert hits, "expected at least one jane-tagged hit"
    for h in hits:
        assert "people/jane-smith" in h.entities
