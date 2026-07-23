"""
PluginsView — placeholder page listing registered tools.

Shows each registered tool's name, description, and action
count from the Registry. No editing — read-only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from core.registry import Registry

_TOOL_ICONS: dict[str, str] = {
    "browser":  "🌐",
    "windows":  "🪟",
    "file":     "📂",
}


class PluginsView(QWidget):
    """Plugin/tool listing page.

    Args:
        registry: Registry instance for read-only tool info.
    """

    def __init__(
        self,
        registry: "Registry | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._registry = registry
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(12)

        title = QLabel("Plugins")
        title.setProperty("class", "viewTitle")
        root.addWidget(title)

        subtitle = QLabel("Installed tool integrations")
        subtitle.setProperty("class", "viewSubtitle")
        root.addWidget(subtitle)

        root.addSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        container = QWidget()
        self._list_layout = QVBoxLayout(container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()

        scroll.setWidget(container)
        root.addWidget(scroll, stretch=1)

        self._populate()

    def _populate(self) -> None:
        if self._registry is None:
            self._add_label("No registry available.")
            return

        tools = self._registry.list_tools()
        if not tools:
            self._add_label("No tools registered.")
            return

        for name in tools:
            executor = self._registry.get_executor(name)
            if executor is None:
                continue

            card = QFrame()
            card.setProperty("class", "pluginCard")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(6)

            # Top row: icon + name
            top = QHBoxLayout()
            top.setSpacing(10)

            icon = _TOOL_ICONS.get(name, "⚙")
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(
                "font-size: 24px; background: transparent;"
            )
            top.addWidget(icon_lbl)

            name_lbl = QLabel(name.capitalize())
            name_lbl.setProperty("class", "taskTitle")
            top.addWidget(name_lbl)

            top.addStretch()

            actions = executor.get_actions()
            count_lbl = QLabel(f"{len(actions)} action(s)")
            count_lbl.setProperty("class", "taskDetail")
            top.addWidget(count_lbl)

            layout.addLayout(top)

            # Description
            desc_lbl = QLabel(executor.description)
            desc_lbl.setProperty("class", "taskDetail")
            desc_lbl.setWordWrap(True)
            layout.addWidget(desc_lbl)

            # Action list
            for action_name, action_desc in actions.items():
                a_lbl = QLabel(f"  • {action_name}: {action_desc}")
                a_lbl.setProperty("class", "settingsValue")
                a_lbl.setWordWrap(True)
                layout.addWidget(a_lbl)

            idx = self._list_layout.count() - 1
            self._list_layout.insertWidget(idx, card)

    def _add_label(self, text: str) -> None:
        lbl = QLabel(text)
        lbl.setProperty("class", "viewSubtitle")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        idx = self._list_layout.count() - 1
        self._list_layout.insertWidget(idx, lbl)
