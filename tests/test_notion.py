"""Tests for adapters/notion property builders + config resolution.

We don't hit the live Notion API here — all tests exercise pure helpers.
Integration coverage comes from the manual live run documented in the
commit message.
"""
from __future__ import annotations

import pytest

from mcs.adapters.notion import (
    NotionConfigError,
    _cfg,
    _date,
    _headers,
    _multi_select,
    _number,
    _relation,
    _rich_text,
    _select,
    _status,
    _title,
)


# ─── property builders ─────────────────────────────────────────────────

def test_title_wraps_into_notion_shape() -> None:
    assert _title("Hello") == {
        "title": [{"type": "text", "text": {"content": "Hello"}}]
    }


def test_rich_text_truncates_at_2000_chars() -> None:
    long = "x" * 3000
    out = _rich_text(long)
    assert len(out["rich_text"][0]["text"]["content"]) == 2000


def test_number_handles_none() -> None:
    assert _number(None) == {"number": None}
    assert _number(3.5) == {"number": 3.5}
    assert _number(10) == {"number": 10.0}


def test_select_none_when_empty() -> None:
    assert _select(None) == {"select": None}
    assert _select("") == {"select": None}
    assert _select("active") == {"select": {"name": "active"}}


def test_status_uses_status_key_not_select() -> None:
    assert _status("todo") == {"status": {"name": "todo"}}
    assert _status(None) == {"status": None}


def test_multi_select_filters_empty() -> None:
    out = _multi_select(["a", "", "b", None])
    assert out == {"multi_select": [{"name": "a"}, {"name": "b"}]}


def test_date_start_only() -> None:
    assert _date("2026-04-23") == {"date": {"start": "2026-04-23"}}


def test_date_start_plus_end() -> None:
    assert _date("2026-04-23", "2026-04-24") == {
        "date": {"start": "2026-04-23", "end": "2026-04-24"}
    }


def test_date_none_when_no_start() -> None:
    assert _date(None) == {"date": None}


def test_relation_filters_falsy_ids() -> None:
    assert _relation(["p1", "", "p2", None]) == {
        "relation": [{"id": "p1"}, {"id": "p2"}]
    }


def test_headers_shape() -> None:
    h = _headers("secret-token")
    assert h["Authorization"] == "Bearer secret-token"
    assert h["Notion-Version"] == "2022-06-28"
    assert h["Content-Type"] == "application/json"


# ─── config resolution ─────────────────────────────────────────────────

def test_cfg_raises_when_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing MCS_NOTION_TOKEN is surfaced as NotionConfigError."""
    from mcs.config import Settings
    monkeypatch.setattr(Settings, "load", classmethod(lambda cls: cls(
        mcs_notion_token=None,
        mcs_notion_okr_master_db="x",
        mcs_notion_kr_tracker_db="y",
        mcs_notion_daily_tasks_db="z",
        mcs_notion_captures_db="w",
    )))
    with pytest.raises(NotionConfigError, match="MCS_NOTION_TOKEN"):
        _cfg()


def test_cfg_raises_when_any_db_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from mcs.config import Settings
    monkeypatch.setattr(Settings, "load", classmethod(lambda cls: cls(
        mcs_notion_token="t",
        mcs_notion_okr_master_db="a",
        mcs_notion_kr_tracker_db=None,
        mcs_notion_daily_tasks_db="c",
        mcs_notion_captures_db="d",
    )))
    with pytest.raises(NotionConfigError, match="MCS_NOTION_KR_TRACKER_DB"):
        _cfg()


def test_cfg_returns_populated_when_all_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mcs.config import Settings
    monkeypatch.setattr(Settings, "load", classmethod(lambda cls: cls(
        mcs_notion_token="t",
        mcs_notion_okr_master_db="a",
        mcs_notion_kr_tracker_db="b",
        mcs_notion_daily_tasks_db="c",
        mcs_notion_captures_db="d",
    )))
    cfg = _cfg()
    assert cfg.token == "t"
    assert cfg.okr_master_db == "a"
    assert cfg.kr_tracker_db == "b"
    assert cfg.daily_tasks_db == "c"
    assert cfg.captures_db == "d"
