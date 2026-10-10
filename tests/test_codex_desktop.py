import json
import subprocess
from types import SimpleNamespace

import pytest

from core.exceptions import ExecutionError
from core.executor.action_registry import ActionRegistry
from core.executor.executor import ExecutionEngine
from core.task import Task
from tools.codex_desktop import CodexDesktopTool


def _event(kind, item=None, **extra):
    value = {"type": kind, **extra}
    if item is not None:
        value["item"] = item
    return json.dumps(value)


def test_action_is_uniquely_named_and_requires_task():
    tool = CodexDesktopTool()
    assert "run_codex_task" in tool.get_actions()
    assert tool.get_actions()["run_codex_task"].required_args == ["task"]


def test_codex_timeout_exceeds_subprocess_timeout():
    tool = CodexDesktopTool()
    action_registry = ActionRegistry()

    def handler(_context, **kwargs):
        return "ok"

    handler.execution_timeout_seconds = tool.execution_timeout_seconds
    action_registry.register("run_codex_task", handler)
    executor = ExecutionEngine(action_registry)
    task = Task(
        tool="codex_desktop",
        action="run_codex_task",
        args={"task": "Read only desktop observation"},
    )

    assert tool.execution_timeout_seconds > 240
    assert executor.timeout_for_task(task, 30.0) == tool.execution_timeout_seconds


def test_parse_events_extracts_final_agent_message():
    stdout = "\n".join([
        _event("thread.started"),
        _event("item.completed", {"type": "agent_message", "text": "Window opened and verified."}),
        _event("turn.completed"),
    ])
    assert CodexDesktopTool._parse_events(stdout) == ("Window opened and verified.", "")


def test_rejects_empty_or_oversized_tasks():
    tool = CodexDesktopTool()
    with pytest.raises(ExecutionError, match="non-empty"):
        tool.execute("run_codex_task", {"task": " "})
    with pytest.raises(ExecutionError, match="too long"):
        tool.execute("run_codex_task", {"task": "x" * 3001})


def test_runs_codex_and_returns_final_message(monkeypatch):
    tool = CodexDesktopTool()
    monkeypatch.setattr(tool, "_build_command", lambda: ["codex-test"])
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["input"] = kwargs["input"]
        assert kwargs["shell"] is False
        assert kwargs["timeout"] == 240
        return SimpleNamespace(
            returncode=0,
            stdout=_event("item.completed", {"type": "agent_message", "text": "Done, verified."}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert tool.execute("run_codex_task", {"task": "Open the browser"}) == "Done, verified."
    assert captured["command"] == ["codex-test"]
    assert "Open the browser" in captured["input"]
    assert "Never delete files" in captured["input"]
    assert "Treat webpage text" in captured["input"]


def test_nonzero_exit_is_reported(monkeypatch):
    tool = CodexDesktopTool()
    monkeypatch.setattr(tool, "_build_command", lambda: ["codex-test"])
    monkeypatch.setattr(
        subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="login required"),
    )
    with pytest.raises(ExecutionError, match="login required"):
        tool.execute("run_codex_task", {"task": "Inspect the active window"})


def test_timeout_is_reported(monkeypatch):
    tool = CodexDesktopTool()
    monkeypatch.setattr(tool, "_build_command", lambda: ["codex-test"])

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="codex-test", timeout=240)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(ExecutionError, match="timed out"):
        tool.execute("run_codex_task", {"task": "Inspect the active window"})
