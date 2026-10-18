"""
MainWindow — application shell composing sidebar, header,
stacked view pages, and footer.

The MainWindow is a lightweight container. All business logic
stays in the Agent; all page-specific logic stays in the views.
MainWindow just wires navigation and keyboard shortcuts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.footer import Footer
from gui.header import Header
from gui.qt_event_bridge import QtEventBridge
from gui.sidebar import Sidebar
from gui.themes.theme import ThemeManager, build_stylesheet
from gui.views.chat_view import ChatView
from gui.views.dashboard_view import DashboardView
from gui.views.history_view import HistoryView
from gui.views.logs_view import LogsView
from gui.views.memory_view import MemoryView
from gui.views.missions_view import MissionsView
from gui.views.plugins_view import PluginsView
from gui.views.settings_view import SettingsView

if TYPE_CHECKING:
    from core.agent import Agent


# Page key → stack index
_PAGE_INDEX: dict[str, int] = {
    "chat": 0,
    "memory": 1,
    "history": 2,
    "logs": 3,
    "plugins": 4,
    "settings": 5,
    "dashboard": 6,
    "missions": 7,
}


class MainWindow(QMainWindow):
    # Core events are exposed to GUI consumers through Qt queued signals.
    core_event_received = Signal(object)

    """Primary application window.

    Args:
        agent: Fully constructed Agent instance.
        config_ctx: Dict with read-only context for display.
    """

    def __init__(
        self,
        agent: Agent,
        config_ctx: dict | None = None,
    ) -> None:
        super().__init__()
        self._agent = agent
        self._ctx = config_ctx or {}
        self._event_bridge: QtEventBridge | None = None
        event_bus = self._ctx.get("event_bus")
        if event_bus is not None:
            self._event_bridge = QtEventBridge(event_bus, parent=self)
            self._event_bridge.event_received.connect(
                self.core_event_received, Qt.ConnectionType.QueuedConnection
            )
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
        config = self._ctx.get("config")
        mode = "assistant"
        workspace = ""
        if config is not None:
            mode = getattr(config, "mode", "hybrid")
            if mode == "developer":
                workspace = getattr(config, "workspace_root", "")
        model_state = self._ctx.get("model_state") or getattr(
            self._agent, "model_state", None
        )

        # Header
        self._header = Header(
            model_name=model_name,
            memory_backend=memory_backend,
        )
        right.addWidget(self._header)

        # Stacked pages. Keep legacy page indices stable; new pages are appended.
        self._stack = QStackedWidget()

        self._chat_view = ChatView(self._agent)
        self._stack.addWidget(self._chat_view)       # 0 (legacy)

        self._memory_view = MemoryView(memory=memory)
        self._stack.addWidget(self._memory_view)      # 1 (legacy)

        self._history_view = HistoryView(memory=memory)
        self._stack.addWidget(self._history_view)     # 2 (legacy)

        self._logs_view = LogsView()
        self._stack.addWidget(self._logs_view)        # 3 (legacy)

        self._plugins_view = PluginsView(registry=registry)
        self._stack.addWidget(self._plugins_view)     # 4 (legacy)

        self._settings_view = SettingsView(
            model_name=model_name,
            memory_backend=memory_backend,
            tool_count=tool_count,
        )
        self._stack.addWidget(self._settings_view)    # 5 (legacy)

        self._dashboard_view = DashboardView(
            model_name=model_name,
            memory_backend=memory_backend,
            tool_count=tool_count,
            mode=mode,
            workspace=str(workspace),
            model_state=model_state,
        )
        self._stack.addWidget(self._dashboard_view)    # 6 (original dashboard slot)

        self._missions_view = MissionsView(
            self._ctx.get("mission_db"), registry=registry,
            execution_policy=self._ctx.get("execution_policy"),
            autonomy_service=self._ctx.get("autonomy_service"),
        )
        self._stack.addWidget(self._missions_view)     # 7 (new page)
        self._stack.setCurrentIndex(_PAGE_INDEX["dashboard"])

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
        self._dashboard_view.navigate_requested.connect(self._navigate_to)
        self._dashboard_view.federation_requested.connect(self._show_federation_unavailable)

        # Header settings button → navigate to settings
        self._header.settings_clicked.connect(
            lambda: self._navigate_to("settings")
        )

        # Chat view status → footer
        self._chat_view.status_changed.connect(self._footer.set_status)
        self._chat_view.status_changed.connect(self._dashboard_view.set_runtime_status)
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

    def closeEvent(self, event) -> None:
        """Detach the EventBus subscription before the window is destroyed."""
        if self._event_bridge is not None:
            self._event_bridge.close()
            self._event_bridge = None
        super().closeEvent(event)

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

    def _show_federation_unavailable(self) -> None:
        """Explain that the legacy federation UI is not present in this checkout."""
        QMessageBox.information(
            self,
            "Device Federation",
            "Device Federation is not available in this checkout.",
        )

    # ── Theme ────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        """Apply the current theme stylesheet."""
        self.setStyleSheet(ThemeManager().stylesheet())

    @Slot(object)
    def _on_theme_changed(self, theme) -> None:
        """Re-apply stylesheet when the theme changes."""
        self.setStyleSheet(build_stylesheet(theme))
