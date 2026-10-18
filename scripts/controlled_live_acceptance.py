"""Controlled live acceptance for local provider, browser and desktop tool boundaries.

This script deliberately uses only a local loopback HTTP endpoint and the configured
local LLM provider. It opens a temporary browser tab and a blank Notepad instance;
only a Notepad PID created by this run is eligible for cleanup.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from core.executor.isolated_handler import IsolatedToolHandler
from tools.browser import BrowserTool
from tools.windows import WindowsTool


class _LocalPageHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.server.request_seen.set()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<!doctype html><meta charset='utf-8'><title>JARVIS local browser check</title>"
            b"<p>JARVIS_LIVE_BROWSER_OK</p>"
            b"<script>setTimeout(()=>location.replace('about:blank'),1200)</script>"
        )

    def log_message(self, _format: str, *_args: Any) -> None:
        return


class _LocalHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_seen: threading.Event


def _notepad_pids() -> set[int]:
    result = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"tasklist failed with exit code {result.returncode}")
    pids: set[int] = set()
    for row in csv.reader(result.stdout.splitlines()):
        if len(row) >= 2 and row[0].casefold() == "notepad.exe":
            try:
                pids.add(int(row[1]))
            except ValueError:
                continue
    return pids


def _live_provider_check() -> dict[str, Any]:
    probe = r"""
import json
from config.config import load_config
from core.llm import LLMClient
config = load_config()
response = LLMClient(config).generate(
    "You are a live integration test. Reply with the requested marker only.",
    "Reply exactly with JARVIS_LIVE_PROVIDER_OK",
)
print(json.dumps({
    "provider": config.provider,
    "model": config.model,
    "marker_seen": "JARVIS_LIVE_PROVIDER_OK" in response,
    "response_chars": len(response),
}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=65,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "provider probe failed").strip()
        raise RuntimeError(f"Local provider probe exited {completed.returncode}: {detail[-1500:]}")
    records = [line for line in completed.stdout.splitlines() if line.startswith("{")]
    if not records:
        raise RuntimeError("Local provider probe returned no structured result")
    result = json.loads(records[-1])
    result["status"] = "passed" if result.get("marker_seen") else "failed"
    return result


def _live_browser_check() -> dict[str, Any]:
    server = _LocalHTTPServer(("127.0.0.1", 0), _LocalPageHandler)
    server.request_seen = threading.Event()
    thread = threading.Thread(target=server.serve_forever, name="jarvis-live-http", daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/jarvis-live-check-{uuid.uuid4().hex}"
    try:
        result = IsolatedToolHandler(
            BrowserTool(), "open_url", timeout_seconds=20,
            project_root=REPOSITORY_ROOT,
        )(url=url)
        requested = server.request_seen.wait(timeout=12)
        return {
            "status": "passed" if requested else "failed",
            "tool_result": str(result),
            "local_http_request_observed": requested,
            "external_network_used": False,
            "note": "The temporary local page redirects to about:blank after displaying its marker; a browser tab may remain open.",
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _live_desktop_check() -> dict[str, Any]:
    before = _notepad_pids()
    result = IsolatedToolHandler(
        WindowsTool(), "open_app", timeout_seconds=12,
        project_root=REPOSITORY_ROOT,
    )(app="notepad")
    created: set[int] = set()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        created = _notepad_pids() - before
        if created:
            break
        time.sleep(0.1)
    cleanup_errors: list[str] = []
    for pid in sorted(created):
        cleanup = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if cleanup.returncode != 0:
            cleanup_errors.append(f"PID {pid}: {cleanup.stderr.strip() or cleanup.stdout.strip()}")
    return {
        "status": "passed" if created and not cleanup_errors else "unverified",
        "tool_result": str(result),
        "new_notepad_pids_observed": sorted(created),
        "only_new_pids_targeted_for_cleanup": True,
        "cleanup_errors": cleanup_errors,
        "note": "Existing Notepad PIDs are never terminated. If Windows reuses an existing process, launch acceptance is not treated as independently verified.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Controlled live JARVIS integration checks")
    parser.add_argument(
        "--check", choices=("all", "provider", "browser", "desktop"), default="all",
        help="Run one integration category or all three. Browser opens a temporary loopback tab; desktop launches and cleans up only a newly created Notepad PID.",
    )
    args = parser.parse_args()
    available = {
        "provider": _live_provider_check,
        "browser": _live_browser_check,
        "desktop": _live_desktop_check,
    }
    selected = list(available) if args.check == "all" else [args.check]
    report: dict[str, Any] = {
        "run_id": uuid.uuid4().hex,
        "selected_checks": selected,
        "external_network_used": False,
        "checks": {},
    }
    for name in selected:
        try:
            report["checks"][name] = available[name]()
        except Exception as exc:  # noqa: BLE001 - report each integration failure without hiding later checks
            report["checks"][name] = {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            }
    passed = all(item.get("status") == "passed" for item in report["checks"].values())
    report["overall_status"] = "passed" if passed else "incomplete"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
