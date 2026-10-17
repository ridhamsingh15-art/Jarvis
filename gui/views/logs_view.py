"""
LogsView — live application log viewer.

Installs a custom logging.Handler that routes log records
to a Qt signal, then displays them in a scrollable monospace
QTextEdit with color-coded severity levels.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import (
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class _LogSignalEmitter(QObject):
    """Bridge between Python logging and Qt signals."""

    log_record = Signal(str, str)  # (formatted_text, level_name)


class _QtLogHandler(logging.Handler):
    """Logging handler that emits records via a Qt signal.

    This allows log messages from any thread to appear
    in the GUI without thread-safety issues, since Qt
    signals are queued across thread boundaries.
    """

    def __init__(self, emitter: _LogSignalEmitter) -> None:
        super().__init__()
        self._emitter = emitter
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s │ %(name)-20s │ %(levelname)-7s │ %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            text = self.format(record)
            self._emitter.log_record.emit(text, record.levelname)
        except Exception:
            logging.getLogger(__name__).exception("Error formatting log record")
            self.handleError(record)


_LEVEL_COLORS: dict[str, str] = {
    "DEBUG":    "#8b949e",
    "INFO":     "#c9d1d9",
    "WARNING":  "#d29922",
    "ERROR":    "#f85149",
    "CRITICAL": "#f85149",
}


class LogsView(QWidget):
    """Live log viewer page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._install_handler()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)

        title = QLabel("Logs")
        title.setProperty("class", "viewTitle")
        layout.addWidget(title)

        subtitle = QLabel("Live application log stream")
        subtitle.setProperty("class", "viewSubtitle")
        layout.addWidget(subtitle)

        self._viewer = QTextEdit()
        self._viewer.setObjectName("logViewer")
        self._viewer.setReadOnly(True)
        layout.addWidget(self._viewer, stretch=1)

    def _install_handler(self) -> None:
        """Attach a custom handler to the root logger."""
        self._emitter = _LogSignalEmitter()
        self._emitter.log_record.connect(self._append_log)

        handler = _QtLogHandler(self._emitter)
        handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(handler)

    @Slot(str, str)
    def _append_log(self, text: str, level: str) -> None:
        """Append a colored log line to the viewer.

        Args:
            text: Formatted log message.
            level: Log level name for color coding.
        """
        color = _LEVEL_COLORS.get(level, "#c9d1d9")
        html = f'<span style="color: {color};">{text}</span>'
        self._viewer.append(html)

        # Auto-scroll to bottom
        vbar = self._viewer.verticalScrollBar()
        vbar.setValue(vbar.maximum())
