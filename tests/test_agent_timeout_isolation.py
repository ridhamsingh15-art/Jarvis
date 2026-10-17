"""Regression coverage for Agent tool timeout and future lifecycle."""
from __future__ import annotations

import threading
from unittest.mock import MagicMock

from core.agent import Agent
from core.cognition.conversation import ConversationResponse
from core.execution_policy import ExecutionPolicy
from core.routing.intent_classifier import IntentType
from core.task import Task, TaskStatus


class _BlockingExecutor:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.received_task: Task | None = None

    def execute(self, task: Task) -> Task:
        self.received_task = task
        task.start()
        self.started.set()
        try:
            self.release.wait(timeout=2)
            task.complete("late success")
            return task
        finally:
            self.finished.set()


def test_late_executor_completion_cannot_mutate_timed_out_task() -> None:
    executor = _BlockingExecutor()
    cognitive = MagicMock()
    cognitive.process_fast.return_value = ConversationResponse(
        type="ACTION",
        message="Starting a controlled test action.",
        tool="windows",
        action="open_app",
        parameters={"app": "notepad"},
    )
    agent = Agent(
        planner=MagicMock(),
        validator=MagicMock(),
        executor=executor,
        cognitive_manager=cognitive,
        execution_policy=ExecutionPolicy(allow_destructive_from_core=True),
        default_tool_timeout=0.05,
    )

    try:
        results = agent.run("Run the controlled test action", intent=IntentType.CHAT)
        timed_out_task = next(task for task in results if task.tool == "windows")
        assert executor.started.wait(timeout=1)
        assert timed_out_task.status == TaskStatus.FAILED
        assert "timed out" in timed_out_task.error.lower()

        executor.release.set()
        assert executor.finished.wait(timeout=1)
        assert executor.received_task is not None
        assert executor.received_task is not timed_out_task
        assert executor.received_task.status == TaskStatus.COMPLETED
        assert timed_out_task.status == TaskStatus.FAILED
        assert "timed out" in timed_out_task.error.lower()
    finally:
        executor.release.set()
        agent.close()
