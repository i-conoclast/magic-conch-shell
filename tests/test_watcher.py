"""Unit tests for mcs.adapters.watcher scope + debounce."""
from __future__ import annotations

from pathlib import Path

from mcs.adapters.watcher import _BrainEventHandler, _is_scoped


# ─── _is_scoped ─────────────────────────────────────────────────────────

def test_scoped_signal_md(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    (brain / "signals").mkdir(parents=True)
    f = brain / "signals" / "2026-04-22-foo.md"
    f.touch()
    assert _is_scoped(brain, f) is True


def test_scoped_domain_md(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    (brain / "domains" / "career").mkdir(parents=True)
    f = brain / "domains" / "career" / "x.md"
    f.touch()
    assert _is_scoped(brain, f) is True


def test_not_scoped_outside_brain(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    brain.mkdir()
    f = tmp_path / "elsewhere.md"
    f.touch()
    assert _is_scoped(brain, f) is False


def test_not_scoped_daily_folder(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    (brain / "daily").mkdir(parents=True)
    f = brain / "daily" / "foo.md"
    f.touch()
    assert _is_scoped(brain, f) is False


def test_not_scoped_non_md_extension(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    (brain / "signals").mkdir(parents=True)
    f = brain / "signals" / "foo.txt"
    f.touch()
    assert _is_scoped(brain, f) is False


def test_not_scoped_hidden_file(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    (brain / "signals").mkdir(parents=True)
    f = brain / "signals" / ".hidden.md"
    f.touch()
    assert _is_scoped(brain, f) is False


def test_not_scoped_git_internals(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    (brain / "signals" / ".git").mkdir(parents=True)
    f = brain / "signals" / ".git" / "HEAD.md"
    f.touch()
    assert _is_scoped(brain, f) is False


def test_not_scoped_editor_tilde_backup(tmp_path: Path) -> None:
    """`<stem>~.md` is an editor atomic-save backup (Obsidian/Vim/Emacs)
    that exists only briefly between write and rename; processing it
    races and fires webhooks for a phantom `<stem>~` capture id."""
    brain = tmp_path / "brain"
    (brain / "signals").mkdir(parents=True)
    f = brain / "signals" / "2026-05-02~.md"
    f.touch()
    assert _is_scoped(brain, f) is False


# ─── debounce ───────────────────────────────────────────────────────────

def test_debounce_blocks_rapid_repeats(tmp_path: Path) -> None:
    handler = _BrainEventHandler(tmp_path / "brain", debounce_ms=500)
    p = tmp_path / "x"
    assert handler._should_skip(p) is False    # first fire
    assert handler._should_skip(p) is True     # within window
    assert handler._should_skip(p) is True


def test_debounce_allows_different_paths(tmp_path: Path) -> None:
    handler = _BrainEventHandler(tmp_path / "brain", debounce_ms=500)
    assert handler._should_skip(tmp_path / "a") is False
    assert handler._should_skip(tmp_path / "b") is False


def test_debounce_allows_after_window(tmp_path: Path) -> None:
    handler = _BrainEventHandler(tmp_path / "brain", debounce_ms=10)
    p = tmp_path / "x"
    assert handler._should_skip(p) is False
    import time
    time.sleep(0.02)
    assert handler._should_skip(p) is False
