"""
Window Monitor.

Detects the currently focused application window and recent window history.
Uses platform-specific APIs (Windows only for now), with a safe no-op fallback
on unsupported platforms.
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

from .models import WindowFocusState, WindowInfo

logger = logging.getLogger(__name__)

# Known IDE process names → used to guess workspace path from window title
_IDE_NAMES = frozenset({
    "code", "code.exe",      # VS Code
    "pycharm64", "pycharm",  # PyCharm
    "idea64", "idea",        # IntelliJ
    "vim", "nvim",           # Vim/Neovim
    "sublime_text",          # Sublime Text
    "cursor",                # Cursor AI
    "windsurf",              # Windsurf IDE
})


def _get_focused_window_windows() -> Optional[WindowInfo]:
    """Read focused window on Windows via ctypes/win32api."""
    try:
        import ctypes
        import ctypes.wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        # Get process name
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        try:
            import psutil
            proc = psutil.Process(pid.value)
            app_name = proc.name()
        except Exception:  # noqa: BLE001
            app_name = "unknown"

        app_lower = app_name.lower().replace(".exe", "")
        focus = WindowFocusState.FOCUSED

        # Try to extract workspace path from IDE window title (heuristic)
        # e.g. "main.py — Jarvis [C:\Users\ridha\Projects\Jarvis] — Visual Studio Code"
        workspace_path: Optional[str] = None
        if app_lower in _IDE_NAMES:
            import re
            match = re.search(r"\[([A-Za-z]:\\[^\]]+)\]", title)
            if match:
                workspace_path = match.group(1)

        return WindowInfo(
            title=title,
            application=app_name,
            focus_state=focus,
            workspace_path=workspace_path,
        )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Window detection failed: {e}")
        return None


class WindowMonitor:
    """
    Observes the currently focused window.
    Returns None gracefully on unsupported platforms or when detection fails.
    """

    def observe_focused(self) -> Optional[WindowInfo]:
        if sys.platform == "win32":
            return _get_focused_window_windows()
        # macOS/Linux support can be added via AppleScript / xdotool
        logger.debug("Window monitoring not supported on this platform.")
        return None

    def observe_recent(self) -> list[WindowInfo]:
        """
        Recent window list is not trivially available cross-platform.
        Returns the focused window (if any) as the only 'recent' entry for now.
        """
        focused = self.observe_focused()
        return [focused] if focused else []
