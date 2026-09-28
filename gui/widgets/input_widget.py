"""
InputWidget — multi-line message input with keyboard shortcuts.

A QTextEdit-based input that auto-grows up to 5 lines.
Enter sends, Shift+Enter inserts a newline.

Signals
-------
message_submitted(str)
    Emitted when the user submits a message.
clear_requested()
    Emitted when Ctrl+L is pressed.
focus_requested()
    Emitted when Ctrl+K is pressed.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class _AutoGrowTextEdit(QTextEdit):
    """QTextEdit that grows vertically up to max_lines."""

    submit_requested = Signal()

    def __init__(
        self, max_lines: int = 5, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._max_lines = max_lines
        self._base_height = 44
        self._line_height = 22
        self.setFixedHeight(self._base_height)
        self.textChanged.connect(self._adjust_height)
        self.setAcceptRichText(False)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle Enter (send) vs Shift+Enter (newline)."""
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.submit_requested.emit()
            return
        super().keyPressEvent(event)

    def _adjust_height(self) -> None:
        """Resize height based on content, capped at max_lines."""
        lines = max(1, self.document().blockCount())
        clamped = min(lines, self._max_lines)
        target = self._base_height + (clamped - 1) * self._line_height
        self.setFixedHeight(target)


class InputWidget(QWidget):
    """Professional message input area.

    Contains a multi-line text edit with auto-grow and a send
    button. Emits ``message_submitted`` on Enter or Send click.
    """

    message_submitted = Signal(str)
    clear_requested = Signal()
    focus_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        frame = QFrame()
        frame.setObjectName("inputFrame")

        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(16, 12, 16, 14)
        frame_layout.setSpacing(10)

        self._input = _AutoGrowTextEdit(max_lines=5)
        self._input.setObjectName("messageInput")
        self._input.setPlaceholderText("Ask Jarvis anything...")
        frame_layout.addWidget(self._input, stretch=1)

        self._send_btn = QPushButton("↑")
        self._send_btn.setObjectName("sendButton")
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setFixedSize(40, 40)
        self._send_btn.setToolTip("Send message (Enter)")
        frame_layout.addWidget(
            self._send_btn, alignment=Qt.AlignmentFlag.AlignBottom
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(frame)

    def _connect_signals(self) -> None:
        self._input.submit_requested.connect(self._on_submit)
        self._send_btn.clicked.connect(self._on_submit)
        self._input.textChanged.connect(self._update_send_state)
        self._update_send_state()

    def _on_submit(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        self.message_submitted.emit(text)

    def _update_send_state(self) -> None:
        has_text = bool(self._input.toPlainText().strip())
        self._send_btn.setEnabled(has_text)

    # ── Public API ───────────────────────────────────────────

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the input area.

        Args:
            enabled: True to enable, False to disable.
        """
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(
            enabled and bool(self._input.toPlainText().strip())
        )
        if enabled:
            self._input.setFocus()

    def focus_input(self) -> None:
        """Focus the text input field."""
        self._input.setFocus()
