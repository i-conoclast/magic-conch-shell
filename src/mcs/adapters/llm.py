"""LLM adapter — unified call() that routes to Ollama or Codex OAuth.

Routing precedence (caller-friendly):
  1. explicit `model=` wins
  2. `task=` maps to a default model via TASK_DEFAULTS
  3. otherwise DEFAULT_MODEL ("ollama-local")

`sensitive=True` forces a local provider regardless of the above. Used for
finance / relationships / health-* domain data that must not leave the host.

Exposed through the MCP daemon as a single `llm.call` tool; downstream
semantic wrappers (oracle, brief, entity-extract) live in skills/agents.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mcs.config import load_settings


class LLMError(RuntimeError):
    """Raised when no provider can handle a call (missing creds, down, etc.)."""


@dataclass(frozen=True)
class ModelSpec:
    key: str                  # our stable name ("ollama-local")
    provider: str             # "ollama" | "codex"
    remote_name: str          # how the provider refers to it ("qwen3.6:35b-a3b-mxfp8")


# Model registry. Adding a row here is enough to route to it.
MODELS: dict[str, ModelSpec] = {
    "ollama-local": ModelSpec(
        key="ollama-local",
        provider="ollama",
        remote_name="qwen3.6:35b-a3b-mxfp8",
    ),
    "codex": ModelSpec(
        key="codex",
        provider="codex",
        remote_name="gpt-5.4",
    ),
}

# Task → default model. Skills pick a task label instead of hard-coding
# models so routing policy stays in one place.
TASK_DEFAULTS: dict[str, str] = {
    "oracle": "ollama-local",         # sentence-length answers, local is fine
    "briefing": "codex",              # quality matters, external OK
    "consulting": "codex",            # options + reasoning
    "entity-extract": "ollama-local", # cheap & frequent, local
    "summarize": "ollama-local",
}

DEFAULT_MODEL = "ollama-local"
LOCAL_PROVIDERS = frozenset({"ollama"})


def resolve_model(
    *,
    model: str | None = None,
    task: str | None = None,
    sensitive: bool = False,
) -> ModelSpec:
    """Pick a ModelSpec given routing inputs.

    Precedence: model > task > DEFAULT_MODEL. `sensitive=True` then
    downgrades non-local picks to DEFAULT_MODEL if it's local, else
    raises (so sensitive data never silently leaves the host).
    """
    if model:
        if model not in MODELS:
            raise LLMError(
                f"unknown model {model!r}. Known: {sorted(MODELS)}"
            )
        picked = MODELS[model]
    elif task:
        key = TASK_DEFAULTS.get(task, DEFAULT_MODEL)
        picked = MODELS[key]
    else:
        picked = MODELS[DEFAULT_MODEL]

    if sensitive and picked.provider not in LOCAL_PROVIDERS:
        fallback = MODELS[DEFAULT_MODEL]
        if fallback.provider not in LOCAL_PROVIDERS:
            raise LLMError(
                "sensitive=True but no local provider available in MODELS"
            )
        picked = fallback
    return picked


# ─── Providers ─────────────────────────────────────────────────────────

async def _call_ollama(
    spec: ModelSpec,
    *,
    prompt: str,
    system: str | None,
    temperature: float,
    max_tokens: int | None,
    format_: str | None,
    think: bool | str | None,
) -> dict[str, Any]:
    from ollama import AsyncClient

    settings = load_settings()
    # Ollama SDK expects the base URL without /v1 (it speaks its native API).
    host = settings.ollama_base_url.rstrip("/")
    if host.endswith("/v1"):
        host = host[:-3]

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    options: dict[str, Any] = {"temperature": float(temperature)}
    if max_tokens is not None:
        options["num_predict"] = int(max_tokens)

    client = AsyncClient(host=host)
    chat_kwargs: dict[str, Any] = {
        "model": spec.remote_name,
        "messages": messages,
        "options": options,
        "format": format_ or None,
    }
    # Qwen3.x exposes a `think` toggle — passing through lets callers disable
    # reasoning tokens for short/deterministic tasks where max_tokens is tight.
    if think is not None:
        chat_kwargs["think"] = think
    try:
        resp = await client.chat(**chat_kwargs)
    except Exception as e:
        raise LLMError(f"ollama call failed ({spec.remote_name}): {e}") from e

    text = resp["message"]["content"] if isinstance(resp, dict) else resp.message.content
    return {
        "model": spec.key,
        "provider": "ollama",
        "remote_name": spec.remote_name,
        "text": text,
        # Ollama returns counts in eval_count / prompt_eval_count if available
        "usage": {
            "prompt_tokens": (
                resp.get("prompt_eval_count") if isinstance(resp, dict)
                else getattr(resp, "prompt_eval_count", None)
            ),
            "completion_tokens": (
                resp.get("eval_count") if isinstance(resp, dict)
                else getattr(resp, "eval_count", None)
            ),
        },
    }


async def _call_codex(
    spec: ModelSpec,
    *,
    prompt: str,
    system: str | None,
    temperature: float,
    max_tokens: int | None,
    format_: str | None,
    think: bool | str | None,
) -> dict[str, Any]:
    # OAuth flow and the exact SDK surface get wired when we use this in
    # anger. For now we fail loudly so callers don't silently send external
    # traffic without knowing auth isn't set up.
    raise LLMError(
        "codex provider not wired yet. Use model='ollama-local' for now, "
        "or set task to one that routes local (oracle, entity-extract, summarize)."
    )


# ─── Public API ────────────────────────────────────────────────────────

async def call(
    prompt: str,
    *,
    model: str | None = None,
    task: str | None = None,
    sensitive: bool = False,
    system: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    format_: str | None = None,
    think: bool | str | None = None,
) -> dict[str, Any]:
    """Send a prompt to the chosen LLM and return a normalized result.

    Returns:
        {
          "model": "<our key>",
          "provider": "ollama" | "codex",
          "remote_name": "<provider-specific name>",
          "text": "<completion>",
          "usage": {"prompt_tokens": int|None, "completion_tokens": int|None},
        }
    """
    spec = resolve_model(model=model, task=task, sensitive=sensitive)
    if spec.provider == "ollama":
        return await _call_ollama(
            spec,
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            format_=format_,
            think=think,
        )
    if spec.provider == "codex":
        return await _call_codex(
            spec,
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            format_=format_,
            think=think,
        )
    raise LLMError(f"unsupported provider {spec.provider!r}")
