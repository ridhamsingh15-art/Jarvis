"""
Footer — status strip at the bottom of the application.

Shows a status dot + text (left), connection status (center),
and model / tool count / response time (right).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPainter, QColor, QBrush
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)


class _Dot(QWidget):
    """Tiny painted status dot."""

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


_STATE_MAP: dict[str, tuple[str, str]] = {
    "idle":      ("#3fb950", "Ready"),
    "thinking":  ("#d29922", "Thinking…"),
    "planning":  ("#d29922", "Planning…"),
    "executing": ("#d29922", "Executing…"),
    "completed": ("#3fb950", "Completed"),
    "error":     ("#f85149", "Error"),
}


class Footer(QFrame):
    """Application status footer.

    Args:
        model_name: Current model display name.
        tool_count: Number of loaded tools.
    """

    def __init__(
        self,
        model_name: str = "",
        tool_count: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("footerFrame")
        self._model_name = model_name
        self._tool_count = tool_count
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(8)

        # Left: status dot + text
        self._dot = _Dot()
        self._dot.setObjectName("footerDot")
        layout.addWidget(self._dot)

        self._status_label = QLabel("Ready")
        self._status_label.setProperty("class", "footerText")
        layout.addWidget(self._status_label)

        layout.addStretch()

        # Center: connection
        conn_label = QLabel("● Connected")
        conn_label.setProperty("class", "footerText")
        layout.addWidget(conn_label)

        layout.addStretch()

        # Right: model · tools · response time
        if self._model_name:
            model_lbl = QLabel(self._model_name)
            model_lbl.setProperty("class", "footerText")
            layout.addWidget(model_lbl)

            sep1 = QLabel("·")
            sep1.setProperty("class", "footerText")
            layout.addWidget(sep1)

        tools_lbl = QLabel(f"{self._tool_count} tools")
        tools_lbl.setProperty("class", "footerText")
        layout.addWidget(tools_lbl)

        sep2 = QLabel("·")
        sep2.setProperty("class", "footerText")
        layout.addWidget(sep2)

        self._time_label = QLabel("—")
        self._time_label.setProperty("class", "footerText")
        layout.addWidget(self._time_label)

    @Slot(str)
    def set_status(self, state: str) -> None:
        """Update the status indicator.

        Args:
            state: One of 'idle', 'thinking', 'planning',
                   'executing', 'completed', 'error'.
        """
        color, text = _STATE_MAP.get(state, _STATE_MAP["idle"])
        self._dot.set_color(color)
        self._status_label.setText(text)

    def set_response_time(self, seconds: float) -> None:
        """Display the last response time.

        Args:
            seconds: Response duration in seconds.
        """
        self._time_label.setText(f"{seconds:.1f}s")
