"""Tests for killable process-isolated tool handlers."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from core.executor.isolated_handler import IsolatedHandlerTimeout, IsolatedToolHandler


class StallingTestTool:
    """Pickleable test handler that attempts a side effect after a delay."""

    name = "test_stalling_tool"

    def execute(self, action: str, args: dict) -> str:
        if action != "stall":
            raise ValueError("unexpected action")
        time.sleep(float(args["delay"]))
        Path(args["target"]).write_text("late mutation", encoding="utf-8")
        return "completed"


def test_isolated_handler_terminates_stalled_non_shell_handler(tmp_path: Path) -> None:
    target = tmp_path / "must-not-appear-after-timeout.txt"
    handler = IsolatedToolHandler(StallingTestTool(), "stall", timeout_seconds=0.4)

    started = time.monotonic()
    with pytest.raises(IsolatedHandlerTimeout, match="OUTCOME UNKNOWN"):
        handler(delay=1.5, target=str(target))
    elapsed = time.monotonic() - started

    assert elapsed < 2.0
    # Give a leaked child enough time to perform the delayed write if it survived.
    time.sleep(1.7)
    assert not target.exists()


def test_isolated_handler_returns_real_tool_result(tmp_path: Path) -> None:
    from tools.file import FileTool

    target = tmp_path / "isolated-create.txt"
    handler = IsolatedToolHandler(FileTool(workspace_root=tmp_path), "write_file", timeout_seconds=5)
    result = handler(path=str(target), content="created in child process")

    assert target.read_text(encoding="utf-8") == "created in child process"
    assert "wrote 24 character" in str(result).lower()



def test_shell_handler_runs_in_isolated_worker_and_preserves_structured_result(tmp_path: Path) -> None:
    from tools.shell import ShellTool

    tool = ShellTool(workspace_root=tmp_path, timeout_seconds=5, allowed_commands=["python"])
    handler = IsolatedToolHandler(
        tool, "run", mode="shell_structured", timeout_seconds=10, project_root=Path(__file__).resolve().parents[1]
    )
    result = handler(command="python --version", cwd=str(tmp_path), timeout=5)

    assert isinstance(result, dict)
    assert result["exit_code"] == 0
    assert "python" in result["stdout"].lower()
    assert result["blocked"] is False
    assert result["timed_out"] is False



def test_agent_does_not_return_before_isolated_worker_deadline(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from core.agent import Agent
    from core.execution_policy import ExecutionPolicy
    from core.executor.action_registry import ActionRegistry
    from core.executor.executor import ExecutionEngine
    from core.task import Task, TaskStatus

    target = tmp_path / "agent-late-side-effect.txt"
    handler = IsolatedToolHandler(StallingTestTool(), "stall", timeout_seconds=0.4)
    registry = ActionRegistry()
    registry.register("open_app", handler)
    engine = ExecutionEngine(registry)
    agent = Agent(
        planner=MagicMock(),
        validator=MagicMock(),
        executor=engine,
        cognitive_manager=MagicMock(),
        execution_policy=ExecutionPolicy(allow_destructive_from_core=True),
        default_tool_timeout=0.05,
    )
    started = time.monotonic()
    try:
        result = agent._process_task(
            Task(
                tool="windows",
                action="open_app",
                args={"delay": 1.5, "target": str(target)},
            )
        )
        elapsed = time.monotonic() - started
        assert result.status == TaskStatus.FAILED
        assert "outcome unknown" in result.error.lower()
        assert elapsed >= 0.3, "Agent returned before the worker's own termination deadline"
        assert elapsed < 1.5
    finally:
        agent.close()

    time.sleep(1.7)
    assert not target.exists()
