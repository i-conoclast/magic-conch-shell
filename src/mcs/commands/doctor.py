"""`mcs doctor` — health-check (FR-I1 / F-80).

One pass through every external piece this project leans on. Each check
returns a status (`ok` / `warn` / `fail`) plus a one-line detail.
`fail` ⇒ non-zero exit; `warn` ⇒ exit 0 with a yellow line. No probes
hit external services unless `--probe` is passed (gateway HEAD-equivalent
+ a minimal Notion users.me call), so the default invocation is safe in
any environment.
"""
from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx
import typer
from rich.console import Console
from rich.table import Table

from mcs.adapters.hermes_client import gateway_url, webhook_url
from mcs.config import load_settings

console = Console()


@dataclass
class CheckResult:
    name: str
    status: str          # "ok" | "warn" | "fail"
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


_OK = "ok"
_WARN = "warn"
_FAIL = "fail"


# ─── individual checks ─────────────────────────────────────────────────

def _check_brain_paths() -> CheckResult:
    s = load_settings()
    brain = s.brain_dir.resolve()
    cache = s.cache_dir.resolve()
    if not brain.exists():
        return CheckResult("brain dir", _FAIL, f"missing: {brain}")
    if not cache.exists():
        return CheckResult(
            "brain dir",
            _WARN,
            f"brain/ ok, but .brain/ missing ({cache}) — daemon will create it.",
        )
    return CheckResult("brain dir", _OK, f"{brain}")


def _check_milvus_db() -> CheckResult:
    s = load_settings()
    db = s.cache_dir.resolve() / "memsearch.db"
    if not db.exists():
        return CheckResult(
            "milvus db",
            _WARN,
            f"{db} not yet created — first capture/index will create it.",
        )
    size_mb = db.stat().st_size / (1024 * 1024)
    return CheckResult("milvus db", _OK, f"{db} ({size_mb:.1f} MB)")


def _port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _check_daemon() -> CheckResult:
    s = load_settings()
    pid_file = s.cache_dir.resolve() / "daemon.pid"
    listening = _port_open(s.daemon_host, s.daemon_port)
    if listening:
        pid = pid_file.read_text(encoding="utf-8").strip() if pid_file.exists() else "?"
        return CheckResult(
            "daemon",
            _OK,
            f"listening on {s.daemon_host}:{s.daemon_port} (pid {pid})",
        )
    if pid_file.exists():
        return CheckResult(
            "daemon",
            _FAIL,
            f"pid file present at {pid_file} but port {s.daemon_port} not listening — stale.",
        )
    return CheckResult(
        "daemon",
        _WARN,
        f"not running. Start with `mcs daemon start --daemon`.",
    )


def _check_hermes_gateway(probe: bool) -> CheckResult:
    url = gateway_url()
    host = url.split("://", 1)[1].split(":", 1)[0]
    port = int(url.rsplit(":", 1)[1])
    if not _port_open(host, port):
        return CheckResult(
            "hermes gateway",
            _WARN,
            f"{url} not reachable (run `hermes gateway run` if you need agent skills).",
        )
    if not probe:
        return CheckResult("hermes gateway", _OK, f"port open at {url}")
    try:
        r = httpx.get(f"{url}/v1/health", timeout=2.0)
    except httpx.HTTPError as e:
        return CheckResult("hermes gateway", _WARN, f"port open but probe failed: {e}")
    if r.status_code >= 500:
        return CheckResult(
            "hermes gateway", _WARN, f"probe got {r.status_code}: {r.text[:80]}"
        )
    return CheckResult("hermes gateway", _OK, f"probe {r.status_code} on {url}")


def _check_hermes_webhook() -> CheckResult:
    s = load_settings()
    enabled = s.entity_extract_webhook_enabled or s.domain_classify_webhook_enabled
    if not enabled:
        return CheckResult(
            "hermes webhook",
            _OK,
            "no webhook subscriptions enabled (extractors off).",
        )
    url = webhook_url(s.entity_extract_webhook_route)
    host = url.split("://", 1)[1].split(":", 1)[0]
    port = int(url.split(":", 2)[2].split("/", 1)[0])
    if not _port_open(host, port):
        return CheckResult(
            "hermes webhook",
            _FAIL,
            f"webhook port {host}:{port} closed but extractors expect it.",
        )
    return CheckResult("hermes webhook", _OK, f"port open at {host}:{port}")


def _check_notion_creds(probe: bool) -> CheckResult:
    s = load_settings()
    missing = [
        k for k, v in [
            ("MCS_NOTION_TOKEN", s.mcs_notion_token),
            ("MCS_NOTION_OKR_MASTER_DB", s.mcs_notion_okr_master_db),
            ("MCS_NOTION_KR_TRACKER_DB", s.mcs_notion_kr_tracker_db),
            ("MCS_NOTION_DAILY_TASKS_DB", s.mcs_notion_daily_tasks_db),
            ("MCS_NOTION_CAPTURES_DB", s.mcs_notion_captures_db),
        ]
        if not v
    ]
    if missing:
        return CheckResult(
            "notion creds",
            _WARN,
            f"missing: {', '.join(missing)}",
        )
    if not probe:
        return CheckResult("notion creds", _OK, "all 5 vars set (not probed)")
    try:
        r = httpx.get(
            "https://api.notion.com/v1/users/me",
            headers={
                "Authorization": f"Bearer {s.mcs_notion_token}",
                "Notion-Version": "2022-06-28",
            },
            timeout=4.0,
        )
    except httpx.HTTPError as e:
        return CheckResult("notion creds", _FAIL, f"probe failed: {e}")
    if r.status_code >= 400:
        return CheckResult(
            "notion creds", _FAIL, f"probe rejected with {r.status_code}: {r.text[:80]}"
        )
    return CheckResult("notion creds", _OK, f"probe ok ({r.status_code})")


def _check_hermes_api_key() -> CheckResult:
    if os.environ.get("HERMES_API_KEY"):
        return CheckResult("hermes api key", _OK, "HERMES_API_KEY set in env")
    dotenv = Path.home() / ".hermes" / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            if line.startswith("API_SERVER_KEY=") and line.split("=", 1)[1].strip():
                return CheckResult("hermes api key", _OK, f"API_SERVER_KEY in {dotenv}")
    return CheckResult(
        "hermes api key",
        _WARN,
        "no HERMES_API_KEY env nor API_SERVER_KEY in ~/.hermes/.env",
    )


# ─── runner ────────────────────────────────────────────────────────────

def _all_checks(probe: bool) -> list[CheckResult]:
    checks: list[Callable[[], CheckResult]] = [
        _check_brain_paths,
        _check_milvus_db,
        _check_daemon,
        lambda: _check_hermes_gateway(probe),
        _check_hermes_webhook,
        _check_hermes_api_key,
        lambda: _check_notion_creds(probe),
    ]
    return [c() for c in checks]


_GLYPH = {_OK: "[green]✓[/green]", _WARN: "[yellow]⚠[/yellow]", _FAIL: "[red]✗[/red]"}


def doctor_cmd(
    probe: bool = typer.Option(
        False, "--probe",
        help="Hit Hermes /v1/health and Notion /users/me (network calls).",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit raw JSON."),
) -> None:
    """One-pass health check across brain/, daemon, Hermes, Notion."""
    results = _all_checks(probe)

    if as_json:
        typer.echo(
            json.dumps(
                [r.to_dict() for r in results], ensure_ascii=False, indent=2
            )
        )
    else:
        t = Table(show_header=True, header_style="bold")
        t.add_column("", width=2)
        t.add_column("check", style="cyan")
        t.add_column("detail")
        for r in results:
            t.add_row(_GLYPH[r.status], r.name, r.detail)
        console.print(t)

    if any(r.status == _FAIL for r in results):
        raise typer.Exit(code=1)
