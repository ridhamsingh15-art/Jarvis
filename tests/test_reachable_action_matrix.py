"""Entry-point and action-registration security matrix for the real JARVIS runtime."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.execution_policy import (
    CapabilitySource,
    ExecutionPolicy,
    PolicyContext,
    PolicyVerdict,
)
from mission_control.crash_cli import _engine

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_CRASH_SAFE_ACTIONS = {
    "browser.open_site",
    "browser.open_url",
    "browser.search_google",
    "codex_desktop.run_codex_task",
    "file.append_line",
    "file.copy",
    "file.create_file",
    "file.create_folder",
    "file.delete",
    "file.directory_file_stats",
    "file.edit_file",
    "file.ensure_text_files",
    "file.extension_counts",
    "file.list_directory",
    "file.list_directory_details",
    "file.list_largest_files",
    "file.move",
    "file.open_file",
    "file.patch_file",
    "file.read_file",
    "file.rename",
    "file.summarize_files",
    "file.write_file",
    "shell.run",
    "windows.open_app",
}


def test_crash_safe_registered_action_inventory_is_explicit_and_resolvable(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    actions = set(engine.registered_actions())
    assert actions == EXPECTED_CRASH_SAFE_ACTIONS
    for action in sorted(actions):
        assert callable(engine._registry.get(action))


@pytest.mark.parametrize(
    ("source", "tool", "action"),
    [
        (CapabilitySource.PLUGIN, "file", "delete"),
        (CapabilitySource.PLUGIN, "file", "write_file"),
        (CapabilitySource.PLUGIN, "shell", "run"),
        (CapabilitySource.MCP, "file", "delete"),
        (CapabilitySource.MCP, "file", "patch_file"),
        (CapabilitySource.MCP, "shell", "run"),
        (CapabilitySource.SKILL, "file", "delete"),
        (CapabilitySource.SKILL, "file", "append_line"),
    ],
)
def test_untrusted_sources_cannot_mutate_files_or_launch_shell(
    source: CapabilitySource, tool: str, action: str
) -> None:
    policy = ExecutionPolicy(allow_destructive_from_core=True)
    result = policy.check(
        PolicyContext(
            tool=tool,
            action=action,
            source=source,
            source_id="matrix-untrusted-source",
            user_confirmed=True,
            args={"path": str(ROOT / "matrix-must-not-change.txt"), "command": "cmd /c echo unsafe"},
        )
    )
    assert result.verdict == PolicyVerdict.DENY


@pytest.mark.parametrize(
    "command",
    [
        "cmd /c del matrix-target.txt",
        "powershell -Command Remove-Item matrix-target.txt",
        "pwsh -Command Remove-Item matrix-target.txt",
        "bash -c 'rm -f matrix-target.txt'",
        "sh -c 'rm -f matrix-target.txt'",
        "cmd /c powershell -Command Remove-Item matrix-target.txt",
        "powershell -Command cmd /c del matrix-target.txt",
    ],
)
def test_nested_shell_policy_bypasses_are_denied(command: str) -> None:
    policy = ExecutionPolicy(allow_destructive_from_core=True)
    result = policy.check(
        PolicyContext(
            tool="shell",
            action="run",
            source=CapabilitySource.CORE,
            user_confirmed=True,
            args={"command": command},
        )
    )
    assert result.verdict == PolicyVerdict.DENY, command


def test_unknown_actions_are_not_registered_even_if_tool_name_is_known(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    with pytest.raises(Exception, match="No execution handler registered"):
        engine._registry.get("file.arbitrary_python")


def test_legacy_mission_user_confirmed_argument_does_not_authorize_delete(tmp_path: Path) -> None:
    from core.execution_policy import ExecutionPolicy
    from core.task import Task
    from mission_control.execution import MissionExecutor
    from mission_control.mission import Mission, MissionState

    target = tmp_path / "legacy-approval-provenance.txt"
    target.write_text("preserve", encoding="utf-8")
    step = json.dumps({
        "tool": "file",
        "action": "delete",
        "args": {"path": str(target), "user_confirmed": True},
    })

    class RecordingEngine:
        called = False

        def execute(self, task: Task) -> Task:
            self.called = True
            task.start()
            task.complete("should never execute")
            return task

    engine = RecordingEngine()
    mission = Mission(
        id="legacy-untrusted-confirmation",
        objective="diagnostic only",
        state=MissionState.RUNNING,
        steps=[step],
    )
    MissionExecutor(
        execution_engine=engine,
        policy=ExecutionPolicy(allow_destructive_from_core=True),
    ).step(mission)

    assert mission.state == MissionState.WAITING_APPROVAL
    assert engine.called is False
    assert target.read_text(encoding="utf-8") == "preserve"



def test_main_runtime_registers_only_process_isolated_builtin_handlers() -> None:
    from config.config import load_config
    from core.executor.isolated_handler import IsolatedToolHandler
    from main import _build_infra

    infra = _build_infra(load_config())
    actions = set(infra.action_registry.list_actions())
    assert actions == {
        "append_line", "copy", "create_file", "create_folder", "delete", "edit_file",
        "execute", "list_directory", "list_largest_files", "move", "open_app",
        "open_file", "open_site", "open_url", "patch_file", "read_file", "rename",
        "run", "search_google", "shell_run", "summarize_files", "write_file",
    }
    assert all(
        isinstance(infra.action_registry.get(action), IsolatedToolHandler)
        for action in actions
    )



def test_legacy_cli_file_actions_are_isolated_and_workspace_bounded(tmp_path: Path) -> None:
    from core.executor.isolated_handler import IsolatedToolHandler
    from core.task import Task, TaskStatus
    from mission_control.cli import _make_engine
    from tools.file import FileTool

    workspace = tmp_path / "legacy-workspace"
    workspace.mkdir()
    outside = tmp_path / "outside-legacy.txt"
    engine = _make_engine(FileTool(workspace_root=workspace))
    assert all(
        isinstance(engine._registry.get(f"file.{action}"), IsolatedToolHandler)
        for action in FileTool(workspace_root=workspace).get_actions()
    )

    task = Task(
        tool="file",
        action="file.create_file",
        args={"path": str(outside), "text": "must not escape"},
    )
    engine.execute(task)
    assert task.status == TaskStatus.FAILED
    assert not outside.exists()
