"""
HistoryView — conversation history grouped by date.

Groups MemoryEntry objects into Today, Yesterday, and Older
sections. Each entry shows timestamp + summary. Read-only.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from memory.sqlite_memory import SqliteMemory

logger = logging.getLogger(__name__)


class HistoryView(QWidget):
    """Conversation history page grouped by date.

    Args:
        memory: SqliteMemory for read-only queries.
    """

    def __init__(
        self,
        memory: SqliteMemory | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._memory = memory
        self._build_ui()
        self._load_history()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(12)

        title = QLabel("History")
        title.setProperty("class", "viewTitle")
        root.addWidget(title)

        subtitle = QLabel("Previous conversations")
        subtitle.setProperty("class", "viewSubtitle")
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_widget)
        root.addWidget(scroll, stretch=1)

    def _load_history(self) -> None:
        if self._memory is None:
            self._add_label("No memory backend available.")
            return

        try:
            entries = self._memory.get_recent(limit=100)
        except Exception:
            logger.exception("Failed to load history")
            self._add_label("Failed to load history.")
            return

        if not entries:
            self._add_label("No conversation history yet.")
            return

        now = datetime.now(timezone.utc)
        today = now.date()
        yesterday = today - timedelta(days=1)

        groups: dict[str, list] = {
            "Today": [],
            "Yesterday": [],
            "Older": [],
        }

        for entry in entries:
            d = entry.timestamp.date()
            if d == today:
                groups["Today"].append(entry)
            elif d == yesterday:
                groups["Yesterday"].append(entry)
            else:
                groups["Older"].append(entry)

        for group_name in ("Today", "Yesterday", "Older"):
            items = groups[group_name]
            if not items:
                continue

            header = QLabel(group_name)
            header.setProperty("class", "sectionHeader")
            idx = self._list_layout.count() - 1
            self._list_layout.insertWidget(idx, header)

            for entry in items:
                card = self._make_card(entry)
                idx = self._list_layout.count() - 1
                self._list_layout.insertWidget(idx, card)

    def _make_card(self, entry) -> QFrame:
        card = QFrame()
        card.setProperty("class", "listItem")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        ts = entry.timestamp.strftime("%H:%M")
        time_label = QLabel(ts)
        time_label.setProperty("class", "bubbleTime")
        layout.addWidget(time_label)

        summary = entry.summary or entry.user_input
        text_label = QLabel(summary)
        text_label.setProperty("class", "settingsLabel")
        text_label.setWordWrap(True)
        layout.addWidget(text_label)

        return card

    def _add_label(self, text: str) -> None:
        lbl = QLabel(text)
        lbl.setProperty("class", "viewSubtitle")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        idx = self._list_layout.count() - 1
        self._list_layout.insertWidget(idx, lbl)
