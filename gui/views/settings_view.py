"""
SettingsView — application settings page.

Displays theme selector, model name, memory backend,
tool count, version, and disabled future toggles.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.themes.amoled import AMOLED_THEME
from gui.themes.dark import DARK_THEME
from gui.themes.light import LIGHT_THEME
from gui.themes.theme import ThemeManager

_THEMES = {
    "Dark": DARK_THEME,
    "Light": LIGHT_THEME,
    "AMOLED": AMOLED_THEME,
}


class SettingsView(QWidget):
    """Settings page.

    Args:
        model_name: Current LLM model name.
        memory_backend: Memory backend type name.
        tool_count: Number of registered tools.
    """

    def __init__(
        self,
        model_name: str = "",
        memory_backend: str = "SQLite",
        tool_count: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._model_name = model_name
        self._memory_backend = memory_backend
        self._tool_count = tool_count
        self._build_ui()

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(8)

        # Title
        title = QLabel("Settings")
        title.setProperty("class", "viewTitle")
        layout.addWidget(title)

        subtitle = QLabel("Configure your Jarvis experience")
        subtitle.setProperty("class", "viewSubtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        # ── Appearance ───────────────────────────────────────
        layout.addWidget(self._section_header("Appearance"))
        layout.addWidget(self._theme_row())

        layout.addSpacing(12)

        # ── Model & Backend ──────────────────────────────────
        layout.addWidget(self._section_header("Model & Backend"))
        layout.addWidget(
            self._info_row("Model", self._model_name or "Not configured")
        )
        layout.addWidget(
            self._info_row("Memory Backend", self._memory_backend)
        )
        layout.addWidget(
            self._info_row("Loaded Tools", str(self._tool_count))
        )

        layout.addSpacing(12)

        # ── About ────────────────────────────────────────────
        layout.addWidget(self._section_header("About"))
        layout.addWidget(self._info_row("Version", "1.0.0"))

        layout.addSpacing(12)

        # ── Future Features ──────────────────────────────────
        layout.addWidget(self._section_header("Experimental"))
        layout.addWidget(
            self._disabled_row("Voice Input", "Coming Soon")
        )
        layout.addWidget(
            self._disabled_row("Vision", "Coming Soon")
        )

        layout.addStretch()

        scroll.setWidget(container)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    # ── Row builders ─────────────────────────────────────────

    @staticmethod
    def _section_header(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("class", "sectionHeader")
        return lbl

    def _theme_row(self) -> QFrame:
        row = QFrame()
        row.setProperty("class", "settingsRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 12, 16, 12)

        label = QLabel("Theme")
        label.setProperty("class", "settingsLabel")
        layout.addWidget(label)

        layout.addStretch()

        combo = QComboBox()
        for name in _THEMES:
            combo.addItem(name)

        # Set current theme
        mgr = ThemeManager()
        current = mgr.theme.name
        index = combo.findText(current)
        if index >= 0:
            combo.setCurrentIndex(index)

        combo.currentTextChanged.connect(self._on_theme_change)
        layout.addWidget(combo)

        return row

    @staticmethod
    def _info_row(label_text: str, value_text: str) -> QFrame:
        row = QFrame()
        row.setProperty("class", "settingsRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 12, 16, 12)

        label = QLabel(label_text)
        label.setProperty("class", "settingsLabel")
        layout.addWidget(label)

        layout.addStretch()

        value = QLabel(value_text)
        value.setProperty("class", "settingsValue")
        layout.addWidget(value)

        return row

    @staticmethod
    def _disabled_row(label_text: str, status: str) -> QFrame:
        row = QFrame()
        row.setProperty("class", "settingsRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 12, 16, 12)

        label = QLabel(label_text)
        label.setProperty("class", "settingsLabel")
        layout.addWidget(label)

        layout.addStretch()

        value = QLabel(status)
        value.setProperty("class", "settingsDisabled")
        layout.addWidget(value)

        return row

    @staticmethod
    def _on_theme_change(name: str) -> None:
        theme = _THEMES.get(name)
        if theme:
            ThemeManager().set_theme(theme)
