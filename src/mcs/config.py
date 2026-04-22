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

    # Daemon (MCP HTTP server that owns MemSearch + watcher)
    daemon_host: str = Field(default="127.0.0.1")
    daemon_port: int = Field(default=18342)

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
            daemon_host=os.environ.get("MCS_DAEMON_HOST", "127.0.0.1"),
            daemon_port=int(os.environ.get("MCS_DAEMON_PORT", "18342")),
        )


def load_settings() -> Settings:
    """Public loader."""
    return Settings.load()
