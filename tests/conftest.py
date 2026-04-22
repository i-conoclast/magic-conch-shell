"""Shared fixtures for magic-conch-shell tests.

`tmp_brain` gives each test an isolated working tree:
- cwd = tmp_path
- brain/    = tmp_path/brain
- .brain/   = tmp_path/.brain
- Settings() picks these up because brain_dir and cache_dir
  both default to `Path("brain").resolve()` / `Path(".brain").resolve()`
  which resolve against the process cwd.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_brain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated brain/ + .brain/ rooted at tmp_path."""
    (tmp_path / "brain").mkdir()
    (tmp_path / ".brain").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path / "brain"
