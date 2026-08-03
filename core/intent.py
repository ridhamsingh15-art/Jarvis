"""Deterministic intent detection for inexpensive, unambiguous commands."""

from __future__ import annotations

import re

from core.task import Task


class IntentDetector:
    """Converts known commands to tasks without invoking an LLM planner."""

    _OPEN_APP = re.compile(
        r"^\s*(?:open|launch|start)\s+(notepad|calculator|chrome)\s*[.!]?\s*$",
        re.IGNORECASE,
    )

    def detect(self, user_input: str) -> Task | None:
        """Detect a known command, returning ``None`` for planner-handled input."""
        match = self._OPEN_APP.match(user_input)
        if match is None:
            return None
        return Task(tool="windows", action="open_app", args={"app": match.group(1).lower()})
