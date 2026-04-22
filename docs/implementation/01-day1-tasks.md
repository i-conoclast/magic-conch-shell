# Day 1 — 스캐폴드 태스크

**목표**: `magic-conch-shell/` 에서 `mcs --help` 실행 가능한 상태.
**예상 시간**: 2~3시간.
**전제**: [Day 0 환경 완료](00-roadmap.md#day-0-체크리스트) — Python 3.13.12, uv, Ollama+MLX, Hermes.

---

## 1. 디렉토리 스캐폴딩

`02-data-model.md` 구조에 맞춰 생성. 빈 폴더에는 `.gitkeep`.

```
magic-conch-shell/
├── SOUL.md                   ← 이미 있음
├── AGENTS.md                 ← 이미 있음
├── USER.md → brain/USER.md   ← 이미 있음 (symlink)
├── README.md                 ← 이미 있음
├── .env.example              ← 신규
├── .gitignore                ← 신규
├── .python-version           ← 신규 (3.13.12)
├── pyproject.toml            ← 신규
├── src/mcs/
│   ├── __init__.py
│   ├── cli.py                ← Typer entry point
│   ├── engine/
│   │   └── __init__.py
│   ├── adapters/
│   │   └── __init__.py
│   ├── commands/
│   │   └── __init__.py
│   └── config.py
├── skills/
│   └── .gitkeep
├── agents/
│   └── .gitkeep
├── commands/
│   └── .gitkeep
├── tools/
│   └── .gitkeep
├── hooks/
│   ├── command/
│   │   └── .gitkeep
│   └── agent/
│       └── .gitkeep
├── mcp/
│   └── .gitkeep
├── templates/
│   └── .gitkeep
├── brain/                    ← 이미 있음 (USER.md만 포함)
└── .brain/
    └── .gitkeep
```

---

## 2. 파일 내용

### 2.1 `.python-version`
```
3.13.12
```

### 2.2 `.gitignore`
```
# Python
__pycache__/
*.pyc
*.pyo
.venv/
*.egg-info/

# User data (not committed)
brain/
!brain/.gitkeep
.brain/

# Secrets
.env
.env.local

# Logs
*.log

# OS
.DS_Store

# IDE
.vscode/
.idea/
.cursor/
```

### 2.3 `.env.example`
```bash
# ─── Notion ───
NOTION_TOKEN=secret_xxxxx
NOTION_DAILY_TASKS_DB=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NOTION_CALENDAR_DB=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# ─── LLM ───
# Codex OAuth 는 Hermes 쪽에서 관리 (~/.hermes/.env). 여기는 mcs 직접 호출용.
# (선택) Anthropic 백업:
# ANTHROPIC_API_KEY=sk-ant-...

# ─── Ollama (로컬) ───
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_DEFAULT_MODEL=qwen3.6:35b-a3b-mxfp8

# ─── plan-tracker MCP ───
# Week 3 구현 완료 후 활성화
# PLAN_TRACKER_MCP_COMMAND=python /Users/sora-hub/Documents/GitHub/plan-tracker/src/mcp/plan_tracker_server.py

# ─── Embedding (BGE-M3 via Ollama or separate) ───
# 자세한 설정은 Day 2 memsearch 검증 후 결정
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3

# ─── Path overrides (기본값이면 생략 가능) ───
# MCS_BRAIN_DIR=/Users/sora-hub/Documents/GitHub/magic-conch-shell/brain
# MCS_CACHE_DIR=/Users/sora-hub/Documents/GitHub/magic-conch-shell/.brain
```

### 2.4 `pyproject.toml`
```toml
[project]
name = "magic-conch-shell"
version = "0.1.0"
description = "Personal life brain + agent — answers to the shell."
requires-python = ">=3.13"

dependencies = [
  # CLI & UX
  "typer[all]>=0.24",
  "rich>=15",

  # File·데이터
  "watchdog>=6",
  "pydantic>=2.13",
  "pyyaml>=6",
  "python-frontmatter>=1.1",

  # HTTP·외부 API
  "httpx>=0.28",
  "notion-client>=3",

  # LLM
  "ollama>=0.6",           # 로컬 LLM 클라이언트 (OpenAI-compat 대체 가능)
  "oauth-codex>=4",        # ⭐ Codex OAuth (GPT-5.4)

  # MCP
  "fastmcp>=3",            # ⭐ MCP 서버 프레임워크

  # Memory engine (Day 2 검증 후 최종 확정)
  "memsearch>=0.3",

  # Time
  "tzdata>=2026.1",
]

[tool.uv]
dev-dependencies = [
  "pytest>=8",
  "pytest-asyncio>=0.25",
  "ruff>=0.8",
  "mypy>=1.15",
]

[project.scripts]
mcs = "mcs.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mcs"]

[tool.ruff]
target-version = "py313"
line-length = 100

[tool.mypy]
python_version = "3.13"
strict_optional = true
```

### 2.5 `src/mcs/cli.py`
```python
"""magic-conch-shell — CLI entry point."""
from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(
    name="mcs",
    help="magic-conch-shell — personal life brain + agent",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()


@app.command()
def version() -> None:
    """Show version."""
    from mcs import __version__
    console.print(f"[cyan]magic-conch-shell[/cyan] [dim]v{__version__}[/dim]")


@app.command()
def hello() -> None:
    """Smoke test — the shell has spoken."""
    console.print("[bold]The shell has spoken.[/bold]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
```

### 2.6 `src/mcs/__init__.py`
```python
"""magic-conch-shell — personal life brain + agent platform."""
__version__ = "0.1.0"
```

### 2.7 `src/mcs/config.py`
```python
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

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from env vars, falling back to defaults."""
        def _env(key: str, default=None):
            return os.environ.get(key, default)

        return cls(
            ollama_base_url=_env("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            ollama_default_model=_env("OLLAMA_DEFAULT_MODEL", "qwen3.6:35b-a3b-mxfp8"),
            embedding_provider=_env("EMBEDDING_PROVIDER", "ollama"),
            embedding_model=_env("EMBEDDING_MODEL", "bge-m3"),
            notion_token=_env("NOTION_TOKEN"),
            notion_daily_tasks_db=_env("NOTION_DAILY_TASKS_DB"),
            notion_calendar_db=_env("NOTION_CALENDAR_DB"),
        )


def load_settings() -> Settings:
    """Public loader."""
    return Settings.load()
```

### 2.8 빈 패키지 파일
`src/mcs/engine/__init__.py`, `src/mcs/adapters/__init__.py`, `src/mcs/commands/__init__.py` — 전부 빈 파일.

### 2.9 `.gitkeep` 파일
- `skills/.gitkeep`
- `agents/.gitkeep`
- `commands/.gitkeep`
- `tools/.gitkeep`
- `hooks/command/.gitkeep`
- `hooks/agent/.gitkeep`
- `mcp/.gitkeep`
- `templates/.gitkeep`
- `.brain/.gitkeep`
- `brain/.gitkeep` (brain은 gitignore인데 gitkeep은 무시 해제)

---

## 3. 실행 절차

```bash
cd /Users/sora-hub/Documents/GitHub/magic-conch-shell

# 1. Python 버전 고정
echo "3.13.12" > .python-version
pyenv local 3.13.12 || echo "OK"    # shims 재계산
python --version   # Python 3.13.12 확인

# 2. uv init (이미 pyproject.toml 있으면 skip)
uv sync

# 3. CLI 동작 테스트
uv run mcs --help
uv run mcs version
uv run mcs hello

# 예상 출력: "The shell has spoken."
```

---

## 4. Git 세팅

```bash
# 이미 있는 파일들 + 새 파일들 초기 커밋
git init
git add .
git commit -m "chore: initial scaffolding

- pyproject.toml, .python-version, .gitignore, .env.example
- src/mcs with Typer CLI entry
- empty dirs: skills, agents, commands, tools, hooks, mcp
- identity files (SOUL.md, AGENTS.md, USER.md symlink) present
- brain/ + .brain/ skeleton with .gitkeep"

# GitHub repo 생성 (llm-server-template-ollama와 동일 스타일)
gh repo create i-conoclast/magic-conch-shell --public \
  --source=. \
  --description "Personal life brain + agent. The shell has spoken." \
  --push
```

---

## 5. 검증 체크리스트

- [ ] `uv run mcs hello` 실행 성공, "The shell has spoken." 출력
- [ ] `uv run mcs version` → v0.1.0 출력
- [ ] `uv run mcs --help` → 도움말 출력
- [ ] `python --version` = 3.13.12
- [ ] `pyproject.toml` 의존성 lock 파일 (`uv.lock`) 생성
- [ ] `.gitignore`에 brain/, .brain/, .env 포함
- [ ] SOUL.md, AGENTS.md, USER.md (symlink) 존재
- [ ] GitHub repo 생성·push 완료
- [ ] `.env.example` 있음 (.env 없음)

---

## 6. Day 1 완료 후 Day 2 준비

Day 2는 **memsearch 검증** — 별도 체크리스트:

- [ ] memsearch Python SDK 설치 (`uv add memsearch`)
- [ ] Milvus Lite 내장 동작 확인
- [ ] BGE-M3 임베딩 호출 (Ollama 통해서)
- [ ] 한국어 샘플 10개 인덱싱
- [ ] 한국어 쿼리 관련도 정성 평가

**🔴 Day 2 실패 시 즉시 플랜 B 전환 판단.** 감정적 미련 금지.

---

## 7. 주의사항

- **brain/USER.md symlink 깨지지 않게**: `git add` 시 symlink 자체를 추가 (파일 복사 X). `git ls-files -s USER.md`로 mode 120000 (symlink) 확인.
- **.env 절대 커밋 금지**: 시크릿 포함. `.env.example`만 공개.
- **Python 3.13.12 고정**: `.python-version` 파일이 있어야 pyenv가 자동 선택.
- **uv 우선**: pip/poetry/conda 섞지 말 것.
