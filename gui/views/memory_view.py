"""
MemoryView — read-only memory browser with search.

Displays stored MemoryEntry objects from the SQLite backend.
Supports keyword search. All data is read-only.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from memory.sqlite_memory import SqliteMemory

logger = logging.getLogger(__name__)


class MemoryView(QWidget):
    """Memory browser page.

    Args:
        memory: SqliteMemory instance for read-only queries.
    """

    def __init__(
        self,
        memory: "SqliteMemory | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._memory = memory
        self._build_ui()
        self._load_entries()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(12)

        # Title
        title = QLabel("Memory")
        title.setProperty("class", "viewTitle")
        root.addWidget(title)

        subtitle = QLabel("Stored conversation memories (read-only)")
        subtitle.setProperty("class", "viewSubtitle")
        root.addWidget(subtitle)

        # Search
        self._search = QLineEdit()
        self._search.setObjectName("searchInput")
        self._search.setPlaceholderText("Search memories…")
        self._search.textChanged.connect(self._on_search)
        root.addWidget(self._search)

        # Scrollable list
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

    def _load_entries(self, query: str = "") -> None:
        """Load memory entries into the list.

        Args:
            query: Optional search term to filter entries.
        """
        # Clear existing
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._memory is None:
            self._add_empty_state("No memory backend available.")
            return

        try:
            if query:
                entries = self._memory.search(query, limit=50)
            else:
                entries = self._memory.get_recent(limit=50)
        except Exception as exc:
            logger.warning("Failed to load memories: %s", exc)
            self._add_empty_state("Failed to load memories.")
            return

        if not entries:
            self._add_empty_state(
                "No memories found." if query else "No memories stored yet."
            )
            return

        for entry in entries:
            card = self._make_entry_card(entry)
            idx = self._list_layout.count() - 1
            self._list_layout.insertWidget(idx, card)

    def _make_entry_card(self, entry) -> QFrame:
        """Create a card for a single MemoryEntry."""
        card = QFrame()
        card.setProperty("class", "listItem")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        # Timestamp
        ts = entry.timestamp.strftime("%Y-%m-%d %H:%M")
        time_label = QLabel(ts)
        time_label.setProperty("class", "bubbleTime")
        layout.addWidget(time_label)

        # User input
        input_label = QLabel(entry.user_input)
        input_label.setProperty("class", "settingsLabel")
        input_label.setWordWrap(True)
        layout.addWidget(input_label)

        # Summary
        if entry.summary:
            summary_label = QLabel(entry.summary)
            summary_label.setProperty("class", "settingsValue")
            summary_label.setWordWrap(True)
            layout.addWidget(summary_label)

        return card

    def _add_empty_state(self, text: str) -> None:
        lbl = QLabel(text)
        lbl.setProperty("class", "viewSubtitle")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        idx = self._list_layout.count() - 1
        self._list_layout.insertWidget(idx, lbl)

    def _on_search(self, text: str) -> None:
        self._load_entries(text.strip())
