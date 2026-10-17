"""
TaskCard — beautiful card displaying a single Task result.

Shows tool icon, action description, status badge, and
optional duration. Used inside the chat flow to present
multi-task execution results.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.task import Task, TaskStatus

_TOOL_ICONS: dict[str, str] = {
    "browser":  "🌐",
    "windows":  "🪟",
    "file":     "📂",
    "system":   "⚙",
}

_STATUS_CONFIG: dict[TaskStatus, tuple[str, str, str]] = {
    # status → (emoji, label, color)
    TaskStatus.COMPLETED: ("✅", "Completed", "#3fb950"),
    TaskStatus.FAILED:    ("❌", "Failed",    "#f85149"),
    TaskStatus.RUNNING:   ("⏳", "Running",   "#d29922"),
    TaskStatus.PENDING:   ("⏳", "Pending",   "#8b949e"),
}


class TaskCard(QFrame):
    """A styled card widget showing one Task's result.

    Args:
        task: The Task object to display.
        duration: Optional execution duration in seconds.
    """

    def __init__(
        self,
        task: Task,
        duration: float | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("taskCard")
        self._build(task, duration)

    def _build(self, task: Task, duration: float | None) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        # Top row: icon + tool name + action
        top = QHBoxLayout()
        top.setSpacing(10)

        icon = _TOOL_ICONS.get(task.tool, "⚙")
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 20px; background: transparent;")
        top.addWidget(icon_label)

        info = QVBoxLayout()
        info.setSpacing(2)

        title = QLabel(f"{task.tool.capitalize()}")
        title.setProperty("class", "taskTitle")
        info.addWidget(title)

        action_text = task.action.replace("_", " ").capitalize()
        detail = QLabel(action_text)
        detail.setProperty("class", "taskDetail")
        info.addWidget(detail)

        top.addLayout(info, stretch=1)
        layout.addLayout(top)

        # Result or error text
        if task.status == TaskStatus.COMPLETED and task.result:
            result_label = QLabel(str(task.result))
            result_label.setProperty("class", "taskDetail")
            result_label.setWordWrap(True)
            layout.addWidget(result_label)
        elif task.status == TaskStatus.FAILED and task.error:
            err_label = QLabel(f"Error: {task.error}")
            err_label.setProperty("class", "taskDetail")
            err_label.setStyleSheet(
                err_label.styleSheet() + " color: #f85149;"
            )
            err_label.setWordWrap(True)
            layout.addWidget(err_label)

        # Bottom row: status badge + duration
        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        emoji, status_text, color = _STATUS_CONFIG.get(
            task.status, ("❓", "Unknown", "#8b949e")
        )
        badge = QLabel(f"{emoji} {status_text}")
        badge.setProperty("class", "taskBadge")
        badge.setStyleSheet(
            f"color: {color}; background: transparent;"
        )
        bottom.addWidget(badge)

        bottom.addStretch()

        if duration is not None:
            dur_label = QLabel(f"{duration:.1f}s")
            dur_label.setProperty("class", "taskDetail")
            bottom.addWidget(dur_label)

        layout.addLayout(bottom)
