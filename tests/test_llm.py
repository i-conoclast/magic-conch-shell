"""Unit + integration tests for the LLM adapter."""
from __future__ import annotations

import httpx
import pytest

from mcs.adapters.llm import (
    DEFAULT_MODEL,
    LLMError,
    MODELS,
    TASK_DEFAULTS,
    call,
    resolve_model,
)


# ─── pure routing (no network) ──────────────────────────────────────────

def test_explicit_model_wins() -> None:
    spec = resolve_model(model="ollama-local", task="briefing")
    assert spec.key == "ollama-local"


def test_task_default_used_when_no_model() -> None:
    spec = resolve_model(task="oracle")
    assert spec.key == TASK_DEFAULTS["oracle"]


def test_no_inputs_falls_back_to_default() -> None:
    assert resolve_model().key == DEFAULT_MODEL


def test_unknown_task_falls_back_to_default() -> None:
    assert resolve_model(task="make-coffee").key == DEFAULT_MODEL


def test_unknown_model_raises() -> None:
    with pytest.raises(LLMError, match="unknown model"):
        resolve_model(model="llama-9000")


def test_sensitive_downgrades_remote_pick_to_local() -> None:
    # 'briefing' task maps to codex (remote); sensitive must force local.
    spec = resolve_model(task="briefing", sensitive=True)
    assert spec.provider == "ollama"
    assert spec.key == DEFAULT_MODEL


def test_sensitive_leaves_local_pick_alone() -> None:
    spec = resolve_model(model="ollama-local", sensitive=True)
    assert spec.key == "ollama-local"


def test_registry_has_expected_entries() -> None:
    assert "ollama-local" in MODELS
    assert "codex" in MODELS
    assert MODELS["ollama-local"].provider == "ollama"


# ─── Ollama integration (skip if daemon not reachable) ─────────────────

def _ollama_reachable() -> bool:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
    except Exception:
        return False
    if r.status_code != 200:
        return False
    names = {m.get("name", "") for m in r.json().get("models", [])}
    return any(n.startswith(MODELS["ollama-local"].remote_name.split(":")[0]) for n in names)


ollama_required = pytest.mark.skipif(
    not _ollama_reachable(),
    reason="Ollama + configured model not reachable on localhost:11434",
)


@ollama_required
@pytest.mark.asyncio
async def test_call_ollama_returns_text() -> None:
    # Qwen3.6 is a reasoning model — it spends tokens on internal thinking
    # before emitting content. Keep max_tokens generous so we actually see
    # the visible answer.
    out = await call(
        "Reply with exactly the word OK.",
        model="ollama-local",
        temperature=0.0,
        max_tokens=256,
    )
    assert out["provider"] == "ollama"
    assert out["model"] == "ollama-local"
    assert isinstance(out["text"], str)
    assert len(out["text"]) > 0


@pytest.mark.asyncio
async def test_codex_provider_raises_until_wired() -> None:
    with pytest.raises(LLMError, match="codex provider not wired"):
        await call("hi", model="codex")