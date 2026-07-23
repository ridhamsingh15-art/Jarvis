"""
Jarvis GUI package.

Provides a PySide6 desktop front-end for the Jarvis agent.
The public entry point is ``launch_gui(agent, config_ctx)``,
which shows a splash screen, applies the theme, opens the
MainWindow, and enters the Qt event loop.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from gui.themes.theme import ThemeManager

if TYPE_CHECKING:
    from core.agent import Agent

__all__ = ["launch_gui"]


def launch_gui(
    agent: "Agent",
    config_ctx: dict | None = None,
) -> None:
    """Launch the Jarvis desktop GUI.

    Shows a splash screen during initialization, then opens
    the MainWindow. Blocks until the window is closed.

    Args:
        agent: A fully constructed Agent instance. The GUI
               calls ``agent.run()`` and nothing else.
        config_ctx: Read-only context dict for display purposes
                    (model_name, memory_backend, tool_count,
                     registry, memory).
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Jarvis")

    # Apply theme before any widgets are created
    mgr = ThemeManager()
    app.setStyleSheet(mgr.stylesheet())

    # Show splash
    from gui.splash import SplashScreen

    splash = SplashScreen()
    splash.center_on_screen()
    splash.show()
    app.processEvents()

    # Simulate loading steps
    splash.set_step(0)
    app.processEvents()

    splash.set_step(1)
    app.processEvents()

    splash.set_step(2)
    app.processEvents()

    splash.set_step(3)
    app.processEvents()

    # Create main window
    from gui.main_window import MainWindow

    window = MainWindow(agent, config_ctx=config_ctx)

    # Prevent the app from quitting when the splash closes (at 400ms)
    # before the main window is shown (at 500ms).
    app.setQuitOnLastWindowClosed(False)

    # Finish splash and show window
    splash.finish()

    def on_show():
        window.show()
        app.setQuitOnLastWindowClosed(True)

    QTimer.singleShot(500, on_show)

    sys.exit(app.exec())

