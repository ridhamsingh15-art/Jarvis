"""
Header — top bar showing app title, model info, and connection status.

Displays the Jarvis title, current model name, memory backend
type, a connection status dot, and a settings navigation button.

Signals
-------
settings_clicked()
    Emitted when the settings gear button is pressed.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QBrush
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)


class _Dot(QWidget):
    """Tiny painted status dot for the header."""

    def __init__(
        self, color: str = "#3fb950", size: int = 8,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self._size = size
        self.setFixedSize(size, size)

    def set_color(self, hex_color: str) -> None:
        self._color = QColor(hex_color)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(self._color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, self._size, self._size)
        p.end()


class Header(QFrame):
    """Application header bar.

    Args:
        model_name: Display name of the current LLM model.
        memory_backend: Name of the memory backend (e.g. 'SQLite').
    """

    settings_clicked = Signal()

    def __init__(
        self,
        model_name: str = "",
        memory_backend: str = "SQLite",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("headerFrame")
        self._model_name = model_name
        self._memory_backend = memory_backend
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(12)

        # Title
        title = QLabel("Jarvis")
        title.setObjectName("headerTitle")
        layout.addWidget(title)

        layout.addSpacing(8)

        # Metadata labels
        if self._model_name:
            model_lbl = QLabel(f"Model: {self._model_name}")
            model_lbl.setProperty("class", "headerMeta")
            layout.addWidget(model_lbl)

        mem_lbl = QLabel(f"Memory: {self._memory_backend}")
        mem_lbl.setProperty("class", "headerMeta")
        layout.addWidget(mem_lbl)

        layout.addStretch()

        # Connection dot
        self._dot = _Dot("#3fb950")
        self._dot.setObjectName("headerDot")
        layout.addWidget(
            self._dot, alignment=Qt.AlignmentFlag.AlignVCenter
        )

        conn_lbl = QLabel("Connected")
        conn_lbl.setProperty("class", "headerMeta")
        layout.addWidget(conn_lbl)

        layout.addSpacing(8)

        # Settings button
        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("headerSettingsBtn")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(settings_btn)

    def set_connected(self, connected: bool) -> None:
        """Update the connection status dot.

        Args:
            connected: True for green, False for red.
        """
        self._dot.set_color("#3fb950" if connected else "#f85149")
