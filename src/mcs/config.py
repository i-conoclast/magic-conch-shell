"""Configuration loader — reads .env + defaults."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Runtime settings for magic-conch-shell."""

    # Paths
    repo_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
    brain_dir: Path = Field(default_factory=lambda: Path("brain").resolve())
    cache_dir: Path = Field(default_factory=lambda: Path(".brain").resolve())

    # LLM
    ollama_base_url: str = Field(default="http://localhost:11434/v1")
    ollama_default_model: str = Field(default="qwen3.6:35b-a3b-mxfp8")

    # Embedding
    embedding_provider: str = Field(default="ollama")
    embedding_model: str = Field(default="bge-m3")

    # Notion (lazy — only required when push/read operations happen)
    notion_token: str | None = None
    notion_daily_tasks_db: str | None = None
    notion_calendar_db: str | None = None

    # mcs-owned Notion integration (separate from plan-tracker's):
    #   MCS_NOTION_TOKEN             — integration secret (ntn_...)
    #   MCS_NOTION_OKR_MASTER_DB     — Objective pages
    #   MCS_NOTION_KR_TRACKER_DB     — KR pages (synced from okr / tasks / captures)
    #   MCS_NOTION_DAILY_TASKS_DB    — task pages (plan-tracker-style properties)
    #   MCS_NOTION_CAPTURES_DB       — capture pages (multi-select entities)
    mcs_notion_token: str | None = None
    mcs_notion_okr_master_db: str | None = None
    mcs_notion_kr_tracker_db: str | None = None
    mcs_notion_daily_tasks_db: str | None = None
    mcs_notion_captures_db: str | None = None

    # Daemon (MCP HTTP server that owns MemSearch + watcher)
    daemon_host: str = Field(default="127.0.0.1")
    daemon_port: int = Field(default=18342)

    # Webhook trigger (FR-C1: capture → Hermes entity-extract).
    # Off by default — flip on after registering the subscription via
    #   `hermes webhook subscribe entity-extract --secret <S> --skills entity-extract`
    # and setting MCS_ENTITY_EXTRACT_WEBHOOK_SECRET=<S> here.
    entity_extract_webhook_enabled: bool = Field(default=False)
    entity_extract_webhook_route: str = Field(default="entity-extract")
    entity_extract_webhook_secret: str | None = None

    @property
    def daemon_url(self) -> str:
        """HTTP URL the MCP client uses to reach the daemon."""
        return f"http://{self.daemon_host}:{self.daemon_port}/mcp/"

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from env vars, falling back to defaults."""
        return cls(
            ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            ollama_default_model=os.environ.get(
                "OLLAMA_DEFAULT_MODEL", "qwen3.6:35b-a3b-mxfp8"
            ),
            embedding_provider=os.environ.get("EMBEDDING_PROVIDER", "ollama"),
            embedding_model=os.environ.get("EMBEDDING_MODEL", "bge-m3"),
            notion_token=os.environ.get("NOTION_TOKEN"),
            notion_daily_tasks_db=os.environ.get("NOTION_DAILY_TASKS_DB"),
            notion_calendar_db=os.environ.get("NOTION_CALENDAR_DB"),
            mcs_notion_token=_env_or_hermes_env("MCS_NOTION_TOKEN"),
            mcs_notion_okr_master_db=_env_or_hermes_env("MCS_NOTION_OKR_MASTER_DB"),
            mcs_notion_kr_tracker_db=_env_or_hermes_env("MCS_NOTION_KR_TRACKER_DB"),
            mcs_notion_daily_tasks_db=_env_or_hermes_env("MCS_NOTION_DAILY_TASKS_DB"),
            mcs_notion_captures_db=_env_or_hermes_env("MCS_NOTION_CAPTURES_DB"),
            daemon_host=os.environ.get("MCS_DAEMON_HOST", "127.0.0.1"),
            daemon_port=int(os.environ.get("MCS_DAEMON_PORT", "18342")),
            entity_extract_webhook_enabled=_truthy(
                os.environ.get("MCS_ENTITY_EXTRACT_WEBHOOK_ENABLED")
            ),
            entity_extract_webhook_route=os.environ.get(
                "MCS_ENTITY_EXTRACT_WEBHOOK_ROUTE", "entity-extract"
            ),
            entity_extract_webhook_secret=os.environ.get(
                "MCS_ENTITY_EXTRACT_WEBHOOK_SECRET"
            ),
        )


def _truthy(raw: str | None) -> bool:
    if not raw:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_or_hermes_env(key: str) -> str | None:
    """Resolve an env key from the process env, falling back to ~/.hermes/.env.

    Hermes's gateway loads ~/.hermes/.env, so mcs's HTTP-MCP tools invoked
    through Hermes see those vars. CLI commands spawned directly do not —
    this fallback reads the same file so behaviour matches either path.
    """
    val = os.environ.get(key)
    if val:
        return val
    from pathlib import Path
    dotenv = Path.home() / ".hermes" / ".env"
    if not dotenv.exists():
        return None
    try:
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def load_settings() -> Settings:
    """Public loader."""
    return Settings.load()
