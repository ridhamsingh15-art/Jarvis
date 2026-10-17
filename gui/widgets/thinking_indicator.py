"""
ThinkingIndicator — animated bubble shown during Agent.run().

Cycles through phases: Thinking → Planning → Executing
with animated pulsing dots. Inserted into the chat flow
as a temporary widget and removed when results arrive.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)

_PHASES = ["Thinking", "Planning", "Executing"]


class ThinkingIndicator(QFrame):
    """Animated thinking bubble for the chat flow."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("thinkingBubble")
        self._phase_index = 0
        self._dot_count = 0
        self._build_ui()
        self._start_animation()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self._text = QLabel("Thinking")
        self._text.setObjectName("thinkingText")
        layout.addWidget(self._text)

        self._dots = QLabel("●")
        self._dots.setObjectName("thinkingDots")
        self._dots.setFixedWidth(50)
        layout.addWidget(self._dots)

        layout.addStretch()

    def _start_animation(self) -> None:
        """Start the dot and phase animation timers."""
        # Dot pulse every 400ms
        self._dot_timer = QTimer(self)
        self._dot_timer.timeout.connect(self._update_dots)
        self._dot_timer.start(400)

        # Phase rotation every 3s
        self._phase_timer = QTimer(self)
        self._phase_timer.timeout.connect(self._next_phase)
        self._phase_timer.start(3000)

    def _update_dots(self) -> None:
        self._dot_count = (self._dot_count + 1) % 4
        dots = "●" * max(1, self._dot_count)
        self._dots.setText(dots)

    def _next_phase(self) -> None:
        self._phase_index = (self._phase_index + 1) % len(_PHASES)
        self._text.setText(_PHASES[self._phase_index])

    def set_phase(self, phase: str) -> None:
        """Manually set the current phase text.

        Args:
            phase: Phase label like 'Thinking', 'Planning'.
        """
        self._text.setText(phase)

    def stop(self) -> None:
        """Stop all animation timers."""
        self._dot_timer.stop()
        self._phase_timer.stop()
