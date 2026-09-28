"""
Observer registry.

A lightweight dispatcher that aggregates all monitors into a single
`observe()` call, returning a dict of raw observation data that
WorldSnapshot assembles into a WorldState.
"""
from __future__ import annotations

import logging
from typing import Optional

from .git_monitor import GitMonitor
from .models import GitStatus, ProcessInfo, RegisteredWorkspace, WindowInfo
from .process_monitor import ProcessMonitor
from .window_monitor import WindowMonitor

logger = logging.getLogger(__name__)


class WorldObservers:
    """
    Aggregates all environment observers. Each observer is called
    defensively — a failure in one never blocks the others.
    """

    def __init__(
        self,
        git_monitor: GitMonitor,
        process_monitor: ProcessMonitor,
        window_monitor: WindowMonitor,
    ) -> None:
        self._git = git_monitor
        self._process = process_monitor
        self._window = window_monitor

    def collect_git(self, workspaces: list[RegisteredWorkspace]) -> list[GitStatus]:
        try:
            return self._git.observe_all(workspaces)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Git observation failed: {e}")
            return []

    def collect_processes(self) -> list[ProcessInfo]:
        try:
            return self._process.observe()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Process observation failed: {e}")
            return []

    def collect_focused_window(self) -> Optional[WindowInfo]:
        try:
            return self._window.observe_focused()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Window observation failed: {e}")
            return None

    def collect_recent_windows(self) -> list[WindowInfo]:
        try:
            return self._window.observe_recent()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Recent window observation failed: {e}")
            return []
