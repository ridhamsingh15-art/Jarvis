"""
SplashScreen — branded loading screen shown during bootstrap.

Displays the JARVIS title, version, a progress bar, and
cycling status messages (Loading modules → Memory → Tools →
Starting Agent). Auto-closes when loading completes.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

_STEPS = [
    "Loading modules…",
    "Loading Memory…",
    "Loading Tools…",
    "Starting Agent…",
]


class SplashScreen(QWidget):
    """Frameless splash screen with progress steps.

    Usage::

        splash = SplashScreen()
        splash.show()
        # ... do work ...
        splash.set_step(1)
        # ...
        splash.finish()
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(400, 260)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        frame = QFrame()
        frame.setObjectName("splashFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(8)

        layout.addStretch()

        title = QLabel("JARVIS")
        title.setObjectName("splashTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version = QLabel("v1.0.0")
        version.setObjectName("splashVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        layout.addSpacing(24)

        self._status = QLabel(_STEPS[0])
        self._status.setObjectName("splashStatus")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        layout.addSpacing(8)

        self._progress = QProgressBar()
        self._progress.setObjectName("splashProgress")
        self._progress.setTextVisible(False)
        self._progress.setMinimum(0)
        self._progress.setMaximum(len(_STEPS))
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        layout.addStretch()

        root.addWidget(frame)

    def set_step(self, index: int) -> None:
        """Advance to a numbered loading step.

        Args:
            index: Step index (0-based) into the _STEPS list.
        """
        if 0 <= index < len(_STEPS):
            self._status.setText(_STEPS[index])
            self._progress.setValue(index + 1)

    def finish(self) -> None:
        """Mark loading as complete and close the splash."""
        self._progress.setValue(len(_STEPS))
        self._status.setText("Ready!")
        QTimer.singleShot(400, self.close)

    def center_on_screen(self) -> None:
        """Center the splash on the primary screen."""
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2 + geo.x()
            y = (geo.height() - self.height()) // 2 + geo.y()
            self.move(x, y)
