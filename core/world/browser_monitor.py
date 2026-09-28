"""
Browser Monitor.

Browser state is exposed only through approved plugin integrations
(e.g., a browser extension that pushes tab data via the JARVIS Plugin SDK).
This module provides the data model and an adapter for receiving that data.
Direct browser introspection is intentionally NOT implemented here.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BrowserTab:
    """A single open browser tab — provided by a trusted browser plugin."""
    url: str
    title: str
    is_active: bool = False
    domain: str = ""


class BrowserMonitor:
    """
    Receives browser tab data pushed by an approved browser plugin.
    Never reads browser state directly.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tabs: list[BrowserTab] = []
        self._active_tab: Optional[BrowserTab] = None

    def push_tabs(self, tabs: list[dict]) -> None:
        """
        Called by the browser plugin integration to update tab state.
        Each dict should have: url, title, is_active, domain.
        """
        with self._lock:
            self._tabs = [BrowserTab(**t) for t in tabs]
            self._active_tab = next((t for t in self._tabs if t.is_active), None)
            logger.debug(f"Browser monitor updated: {len(self._tabs)} tabs")

    def get_active_tab(self) -> Optional[BrowserTab]:
        with self._lock:
            return self._active_tab

    def get_tabs(self) -> list[BrowserTab]:
        with self._lock:
            return list(self._tabs)

    def clear(self) -> None:
        with self._lock:
            self._tabs = []
            self._active_tab = None
