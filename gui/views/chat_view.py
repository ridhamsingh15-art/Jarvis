"""
ChatView — main chat page composing ChatWidget, InputWidget,
and ThinkingIndicator. Owns the Agent worker thread.

This is the primary interaction surface. It calls Agent.run()
on a QThread and displays results as chat bubbles and task cards.

Signals
-------
status_changed(str)
    Emitted when the processing state changes.
response_time(float)
    Emitted with the Agent.run() duration in seconds.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QVBoxLayout, QWidget

from core.task import Task, TaskStatus
from gui.widgets.chat_widget import ChatWidget
from gui.widgets.input_widget import InputWidget
from gui.widgets.task_card import TaskCard
from gui.widgets.thinking_indicator import ThinkingIndicator

if TYPE_CHECKING:
    from core.agent import Agent

logger = logging.getLogger(__name__)


# ── Background worker ────────────────────────────────────────


class _AgentWorker(QObject):
    """Runs Agent.run() on a background QThread."""

    finished = Signal(list, float)   # tasks, duration_seconds
    error = Signal(str)

    def __init__(self, agent: Agent, user_input: str) -> None:
        super().__init__()
        self._agent = agent
        self._user_input = user_input

    @Slot()
    def run(self) -> None:
        try:
            start = time.monotonic()
            results = self._agent.run(self._user_input)
            duration = time.monotonic() - start
            self.finished.emit(results, duration)
        except Exception as exc:
            logger.exception("Agent worker error")
            self.error.emit(str(exc))


# ── Chat view ────────────────────────────────────────────────


class ChatView(QWidget):
    """Main chat page.

    Args:
        agent: Fully constructed Agent instance.
    """

    status_changed = Signal(str)
    response_time = Signal(float)

    def __init__(
        self, agent: Agent, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._agent = agent
        self._thread: QThread | None = None
        self._worker: _AgentWorker | None = None
        self._thinking: ThinkingIndicator | None = None
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._chat = ChatWidget()
        layout.addWidget(self._chat, stretch=1)

        self._input = InputWidget()
        layout.addWidget(self._input)

        # Welcome message
        self._chat.append_message(
            "system",
            "Welcome to **Jarvis** — your Local AI Operating System. "
            "Type a message to get started.",
        )

    def _connect_signals(self) -> None:
        self._input.message_submitted.connect(self._on_send)
        self._input.clear_requested.connect(self._chat.clear_messages)

    # ── Slots ────────────────────────────────────────────────

    @Slot(str)
    def _on_send(self, text: str) -> None:
        """Handle user message submission."""
        self._chat.append_message("user", text)
        self._input.set_enabled(False)

        # Show thinking indicator
        self._thinking = ThinkingIndicator()
        self._chat.add_widget(self._thinking)

        self.status_changed.emit("thinking")
        self._start_worker(text)

    @Slot(list, float)
    def _on_results(self, tasks: list[Task], duration: float) -> None:
        """Display agent results."""
        self._remove_thinking()

        if len(tasks) == 1:
            task = tasks[0]
            if task.status == TaskStatus.COMPLETED:
                self._chat.append_message(
                    "assistant", str(task.result) if task.result else "Done."
                )
            elif task.status == TaskStatus.FAILED:
                self._chat.append_message("error", task.error)
            else:
                status_display = task.status.value if hasattr(task.status, 'value') else str(task.status)
                self._chat.append_message(
                    "system",
                    f"{task.tool}.{task.action} — {status_display}",
                )
        else:
            # Multiple tasks → show task cards
            for task in tasks:
                card = TaskCard(task, duration=duration / max(len(tasks), 1))
                self._chat.add_widget(card)

        self.status_changed.emit("idle")
        self.response_time.emit(duration)
        self._input.set_enabled(True)
        self._cleanup_worker()

    @Slot(str)
    def _on_error(self, error_msg: str) -> None:
        """Display a pipeline-level error."""
        self._remove_thinking()
        self._chat.append_message("error", f"Agent error: {error_msg}")
        self.status_changed.emit("error")
        self._input.set_enabled(True)
        self._cleanup_worker()

    # ── Worker lifecycle ─────────────────────────────────────

    def _start_worker(self, user_input: str) -> None:
        self._thread = QThread()
        self._worker = _AgentWorker(self._agent, user_input)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)

        self._thread.start()

    def _cleanup_worker(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread.deleteLater()
            self._thread = None
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def _remove_thinking(self) -> None:
        if self._thinking is not None:
            self._thinking.stop()
            self._thinking.setParent(None)
            self._thinking.deleteLater()
            self._thinking = None

    # ── Public API ───────────────────────────────────────────

    def clear_chat(self) -> None:
        """Clear the chat history."""
        self._chat.clear_messages()

    def focus_input(self) -> None:
        """Focus the message input field."""
        self._input.focus_input()
