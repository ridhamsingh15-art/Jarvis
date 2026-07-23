"""
Sidebar — vertical navigation panel with page links.

Displays branded header, navigation items with emoji icons,
and emits ``page_changed`` when the user selects a page.
Active state is tracked and visually highlighted.

Signals
-------
page_changed(str)
    Emitted with the page key when the user clicks a nav item.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# (key, emoji, label)
_NAV_ITEMS: list[tuple[str, str, str]] = [
    ("chat",     "💬", "Chat"),
    ("memory",   "🧠", "Memory"),
    ("history",  "📜", "History"),
    ("logs",     "📊", "Logs"),
    ("plugins",  "🔌", "Plugins"),
    ("settings", "⚙",  "Settings"),
]


class Sidebar(QFrame):
    """Collapsible navigation sidebar.

    Args:
        parent: Optional parent widget.
    """

    page_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebarFrame")
        self.setFixedWidth(220)
        self._buttons: dict[str, QPushButton] = {}
        self._active_key: str = "chat"
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(4)

        # Brand header
        brand = QLabel("JARVIS")
        brand.setObjectName("sidebarBrand")
        layout.addWidget(brand)

        version = QLabel("v1.0.0")
        version.setObjectName("sidebarVersion")
        layout.addWidget(version)

        layout.addSpacing(20)

        # Navigation items
        for key, emoji, label in _NAV_ITEMS:
            btn = QPushButton(f"  {emoji}  {label}")
            btn.setProperty("class", "sidebarBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            btn.clicked.connect(
                lambda checked=False, k=key: self._on_click(k)
            )
            layout.addWidget(btn)
            self._buttons[key] = btn

        layout.addStretch()

        # Set initial active state
        self._update_active()

    def _on_click(self, key: str) -> None:
        if key == self._active_key:
            return
        self._active_key = key
        self._update_active()
        self.page_changed.emit(key)

    def _update_active(self) -> None:
        """Update the visual active state on all buttons."""
        for key, btn in self._buttons.items():
            btn.setProperty("active", "true" if key == self._active_key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_active(self, key: str) -> None:
        """Programmatically set the active page.

        Args:
            key: Navigation item key (e.g. 'chat', 'settings').
        """
        if key in self._buttons:
            self._active_key = key
            self._update_active()
