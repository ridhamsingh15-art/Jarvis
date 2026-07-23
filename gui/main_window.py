"""
MainWindow — application shell composing sidebar, header,
stacked view pages, and footer.

The MainWindow is a lightweight container. All business logic
stays in the Agent; all page-specific logic stays in the views.
MainWindow just wires navigation and keyboard shortcuts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.footer import Footer
from gui.header import Header
from gui.sidebar import Sidebar
from gui.themes.theme import ThemeManager, build_stylesheet
from gui.views.chat_view import ChatView
from gui.views.history_view import HistoryView
from gui.views.logs_view import LogsView
from gui.views.memory_view import MemoryView
from gui.views.plugins_view import PluginsView
from gui.views.settings_view import SettingsView

if TYPE_CHECKING:
    from core.agent import Agent
    from core.registry import Registry
    from memory.sqlite_memory import SqliteMemory


# Page key → stack index
_PAGE_INDEX: dict[str, int] = {
    "chat":     0,
    "memory":   1,
    "history":  2,
    "logs":     3,
    "plugins":  4,
    "settings": 5,
}


class MainWindow(QMainWindow):
    """Primary application window.

    Args:
        agent: Fully constructed Agent instance.
        config_ctx: Dict with read-only context for display.
    """

    def __init__(
        self,
        agent: "Agent",
        config_ctx: dict | None = None,
    ) -> None:
        super().__init__()
        self._agent = agent
        self._ctx = config_ctx or {}
        self._configure_window()
        self._build_ui()
        self._connect_signals()
        self._apply_theme()

    # ── Window setup ─────────────────────────────────────────

    def _configure_window(self) -> None:
        self.setWindowTitle("Jarvis — Local AI Operating System")
        self.setMinimumSize(900, 600)
        self.resize(1100, 720)

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralContainer")
        self.setCentralWidget(central)

        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Sidebar
        self._sidebar = Sidebar()
        outer.addWidget(self._sidebar)

        # Right panel: header + pages + footer
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        model_name = self._ctx.get("model_name", "")
        memory_backend = self._ctx.get("memory_backend", "SQLite")
        tool_count = self._ctx.get("tool_count", 0)
        registry = self._ctx.get("registry")
        memory = self._ctx.get("memory")

        # Header
        self._header = Header(
            model_name=model_name,
            memory_backend=memory_backend,
        )
        right.addWidget(self._header)

        # Stacked pages
        self._stack = QStackedWidget()

        self._chat_view = ChatView(self._agent)
        self._stack.addWidget(self._chat_view)       # 0

        self._memory_view = MemoryView(memory=memory)
        self._stack.addWidget(self._memory_view)      # 1

        self._history_view = HistoryView(memory=memory)
        self._stack.addWidget(self._history_view)     # 2

        self._logs_view = LogsView()
        self._stack.addWidget(self._logs_view)        # 3

        self._plugins_view = PluginsView(registry=registry)
        self._stack.addWidget(self._plugins_view)     # 4

        self._settings_view = SettingsView(
            model_name=model_name,
            memory_backend=memory_backend,
            tool_count=tool_count,
        )
        self._stack.addWidget(self._settings_view)    # 5

        right.addWidget(self._stack, stretch=1)

        # Footer
        self._footer = Footer(
            model_name=model_name,
            tool_count=tool_count,
        )
        right.addWidget(self._footer)

        outer.addLayout(right, stretch=1)

    def _connect_signals(self) -> None:
        # Sidebar navigation
        self._sidebar.page_changed.connect(self._on_page_changed)

        # Header settings button → navigate to settings
        self._header.settings_clicked.connect(
            lambda: self._navigate_to("settings")
        )

        # Chat view status → footer
        self._chat_view.status_changed.connect(self._footer.set_status)
        self._chat_view.response_time.connect(
            self._footer.set_response_time
        )

        # Theme changes
        ThemeManager().theme_changed.connect(self._on_theme_changed)

        # Keyboard shortcuts
        QShortcut(
            QKeySequence("Ctrl+L"), self
        ).activated.connect(self._chat_view.clear_chat)

        QShortcut(
            QKeySequence("Ctrl+K"), self
        ).activated.connect(self._focus_chat_input)

    # ── Navigation ───────────────────────────────────────────

    @Slot(str)
    def _on_page_changed(self, key: str) -> None:
        """Switch the stacked widget to the selected page."""
        index = _PAGE_INDEX.get(key, 0)
        self._stack.setCurrentIndex(index)

    def _navigate_to(self, key: str) -> None:
        """Programmatically navigate to a page.

        Args:
            key: Page key (e.g. 'settings', 'chat').
        """
        self._sidebar.set_active(key)
        self._on_page_changed(key)

    def _focus_chat_input(self) -> None:
        """Switch to chat and focus the input."""
        self._navigate_to("chat")
        self._chat_view.focus_input()

    # ── Theme ────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        """Apply the current theme stylesheet."""
        self.setStyleSheet(ThemeManager().stylesheet())

    @Slot(object)
    def _on_theme_changed(self, theme) -> None:
        """Re-apply stylesheet when the theme changes."""
        self.setStyleSheet(build_stylesheet(theme))
