"""
Workspace sub-component stubs.

Groups the small, stub-only workspace trackers and utilities that were
previously scattered across 8 individual files. These are placeholder
implementations until real OS-integration modules are built.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class WorkspaceState:
    running_applications: list[str] = field(default_factory=list)
    open_windows: list[str] = field(default_factory=list)
    browser_tabs: list[str] = field(default_factory=list)
    active_project: str | None = None
    active_repository: str | None = None
    git_branch: str | None = None


@dataclass
class ApplicationState:
    name: str
    pid: int


# ---------------------------------------------------------------------------
# Stub sub-components (previously individual files)
# ---------------------------------------------------------------------------

class ProcessTracker:
    def get_running_processes(self) -> list[str]:
        return ["code.exe", "chrome.exe", "explorer.exe"]


class AppManager:
    def get_apps(self) -> list[ApplicationState]:
        return [
            ApplicationState("VS Code", 1234),
            ApplicationState("Chrome", 5678),
        ]


class WindowTracker:
    def get_active_window(self) -> str:
        return "VS Code - JARVIS"

    def get_open_windows(self) -> list[str]:
        return ["VS Code - JARVIS", "Chrome - GitHub"]


class BrowserTracker:
    def get_tabs(self) -> list[str]:
        return ["https://github.com/jarvis", "https://stackoverflow.com"]


class DesktopLayout:
    def get_monitors(self) -> list[dict]:
        return [{"id": 1, "resolution": "1920x1080", "primary": True}]


class HardwareMonitor:
    def get_stats(self) -> dict[str, float]:
        return {
            "cpu_percent": 15.5,
            "ram_percent": 45.0,
            "gpu_percent": 5.0,
            "battery_percent": 82.0,
        }


class FileWatcher:
    def get_recent_changes(self) -> list[str]:
        return ["workspace/manager.py", "workspace/stubs.py"]


class SessionContext:
    def build_context(self) -> WorkspaceState:
        state = WorkspaceState()
        state.active_project = "JARVIS AIOS"
        state.active_repository = "jarvis"
        state.git_branch = "main"
        return state


class SnapshotManager:
    def __init__(self) -> None:
        self.snapshots: dict[str, str] = {}

    def create(self, state: WorkspaceState) -> str:
        snap_id = f"snap_{int(time.time())}"
        # Serialize with stable keys that tests assert on.
        self.snapshots[snap_id] = json.dumps({
            "project": state.active_project,
            "repository": state.active_repository,
            "git_branch": state.git_branch,
            "applications": state.running_applications,
            "windows": state.open_windows,
            "tabs": state.browser_tabs,
        })
        return snap_id

    def load(self, snap_id: str) -> dict | None:
        raw = self.snapshots.get(snap_id)
        return json.loads(raw) if raw else None
