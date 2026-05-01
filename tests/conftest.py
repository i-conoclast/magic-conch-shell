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


@pytest.fixture(autouse=True)
def _stub_curator_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default-disable subprocess calls inside pin_skill during tests.

    `pin_skill` shells out to `hermes curator pin <slug>` which mutates
    the real ~/.hermes/skills/.usage.json. Tests that exercise
    `okr.spawn_kr_agent` or `skill_suggestion.confirm` would otherwise
    leave real pin entries in the user's Hermes state for synthetic
    test slugs ("2026-Q2-arch-kr-1", etc.).

    We patch the subprocess.run reference *inside* hermes_client (not
    pin_skill itself) so the dedicated pin_skill unit tests can still
    drive their own subprocess.run override and observe success / non-
    zero / FileNotFoundError / TimeoutExpired branches.
    """
    import subprocess as _subprocess

    def _no_real_hermes(args, *, capture_output=True, timeout=10):
        if isinstance(args, (list, tuple)) and args and args[0] == "hermes":
            return _subprocess.CompletedProcess(
                args=args, returncode=0, stdout=b"", stderr=b""
            )
        # Anything else — let the real subprocess handle it.
        return _subprocess.run(  # noqa: S603
            args, capture_output=capture_output, timeout=timeout
        )

    monkeypatch.setattr(
        "mcs.adapters.hermes_client.subprocess.run", _no_real_hermes
    )
