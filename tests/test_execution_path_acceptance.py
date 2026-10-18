"""Adversarial, side-effect-observing acceptance checks for reachable CLI execution.

These tests exercise the actual crash-safe entrypoint and inspect the filesystem afterward.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from mission_control.crash_store import CrashSafeMissionStore

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _invoke(db: Path, mission_id: str, workspace: Path, steps: list[dict], *extra: str):
    return subprocess.run(
        [
            PYTHON, str(ROOT / "mission_crash_safe.py"),
            "--steps-json", json.dumps(steps),
            "--mission", "Adversarial execution-path acceptance test",
            "--mission-id", mission_id,
            "--mission-db", str(db),
            "--workspace-root", str(workspace),
            *extra,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def _approve(db: Path, mission_id: str, workspace: Path):
    return subprocess.run(
        [
            PYTHON, str(ROOT / "mission_crash_safe.py"),
            "--mission-db", str(db),
            "--workspace-root", str(workspace),
            "--approve", mission_id,
            "--step", "1",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


@pytest.mark.parametrize(
    ("action", "args", "expected_absent"),
    [
        ("create_file", {"path": "../escape-created.txt", "text": "MUST_NOT_ESCAPE"}, "escape-created.txt"),
        ("write_file", {"path": "../escape-written.txt", "content": "MUST_NOT_ESCAPE"}, "escape-written.txt"),
        ("create_folder", {"path": "../escape-folder"}, "escape-folder"),
    ],
)
def test_real_cli_file_mutations_cannot_escape_workspace(
    tmp_path: Path, action: str, args: dict, expected_absent: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside_target = tmp_path / expected_absent
    db = tmp_path / "missions.sqlite3"
    result = _invoke(
        db, f"workspace-escape-{action}", workspace,
        [{"id": "escape", "tool": "file", "action": action, "args": args}],
    )
    assert result.returncode != 0, result.stdout + result.stderr
    assert not outside_target.exists(), f"{action} mutated a path outside the configured workspace"
    record = CrashSafeMissionStore(db).step(f"workspace-escape-{action}", 0)
    assert record is not None
    assert record["status"] in {"failed", "needs_review", "blocked"}
    print(f"WORKSPACE_ESCAPE=BLOCKED action={action} side_effect=absent")


def test_real_cli_rename_target_cannot_escape_workspace_after_approval(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "source.txt"
    source.write_text("preserve", encoding="utf-8")
    outside_target = tmp_path / "escaped-renamed.txt"
    db = tmp_path / "missions.sqlite3"
    mission_id = "rename-target-escape"
    steps = [{
        "id": "rename",
        "tool": "file",
        "action": "rename",
        "args": {"path": str(source), "new_name": "../escaped-renamed.txt"},
    }]
    pending = _invoke(db, mission_id, workspace, steps)
    assert pending.returncode != 0, pending.stdout + pending.stderr
    assert "WAITING_APPROVAL" in pending.stdout
    assert source.read_text(encoding="utf-8") == "preserve"
    assert not outside_target.exists()

    approved = _approve(db, mission_id, workspace)
    assert approved.returncode != 0, approved.stdout + approved.stderr
    assert source.exists(), "rename removed the source inside the workspace"
    assert not outside_target.exists(), "rename target escaped the configured workspace"
    print("WORKSPACE_ESCAPE=BLOCKED action=rename target=outside")


def test_real_cli_recursive_shell_delete_cannot_remove_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    marker = workspace / "keep-me.txt"
    marker.write_text("preserve", encoding="utf-8")
    db = tmp_path / "missions.sqlite3"
    command = f'cmd.exe /c rmdir /s /q "{workspace}"'
    steps = [{
        "id": "recursive-delete",
        "tool": "shell",
        "action": "run",
        "args": {"command": command, "cwd": str(workspace), "timeout": 5},
        "user_confirmed": True,
    }]
    result = _invoke(db, "shell-recursive-delete", workspace, steps)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "MISSION_STATE=FAILED" in result.stdout
    assert workspace.is_dir(), "recursive shell deletion removed the workspace"
    assert marker.read_text(encoding="utf-8") == "preserve"
    record = CrashSafeMissionStore(db).step("shell-recursive-delete", 0)
    assert record is not None and record["status"] == "blocked"
    assert "nested command interpreters" in record["error"].lower()
    print("SHELL_POLICY_BYPASS=BLOCKED recursive_delete=not_performed")


@pytest.mark.parametrize("action", ["append_line", "patch_file", "edit_file", "move", "copy", "delete"])
def test_approved_mutating_actions_cannot_escape_workspace(
    tmp_path: Path, action: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "source.txt"
    source.write_text("source-preserved", encoding="utf-8")
    outside_target = tmp_path / "outside-target.txt"
    outside_target.write_text("outside-preserved", encoding="utf-8")
    outside_new = tmp_path / "outside-new.txt"
    db = tmp_path / "missions.sqlite3"
    mission_id = f"approved-escape-{action}"

    if action in {"append_line", "patch_file", "edit_file", "delete"}:
        args = {"path": "../outside-target.txt"}
        if action == "append_line":
            args["line"] = "MUST_NOT_APPEND"
        elif action in {"patch_file", "edit_file"}:
            args.update({"old_text": "outside-preserved", "new_text": "MUST_NOT_PATCH"})
    elif action == "move":
        args = {"path": str(source), "dest": "../outside-new.txt"}
    else:
        args = {"path": str(source), "dest": "../outside-new.txt"}

    pending = _invoke(
        db, mission_id, workspace,
        [{"id": "escape", "tool": "file", "action": action, "args": args}],
    )
    assert pending.returncode != 0, pending.stdout + pending.stderr
    assert "WAITING_APPROVAL" in pending.stdout
    approved = _approve(db, mission_id, workspace)
    assert approved.returncode != 0, approved.stdout + approved.stderr

    assert outside_target.read_text(encoding="utf-8") == "outside-preserved"
    assert source.read_text(encoding="utf-8") == "source-preserved"
    assert not outside_new.exists()
    record = CrashSafeMissionStore(db).step(mission_id, 0)
    assert record is not None
    assert record["status"] in {"blocked", "needs_review", "failed"}
    print(f"WORKSPACE_ESCAPE=BLOCKED action={action} side_effect=absent")



def test_normal_agent_path_does_not_accept_model_authored_confirmation(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from core.agent import Agent
    from core.execution_policy import ExecutionPolicy
    from core.task import Task, TaskStatus

    target = tmp_path / "must-survive.txt"
    target.write_text("preserve", encoding="utf-8")

    class SpyExecutor:
        def __init__(self) -> None:
            self.called = False

        def execute(self, task: Task) -> Task:
            self.called = True
            task.start()
            task.complete("unexpected execution")
            return task

    executor = SpyExecutor()
    agent = Agent(
        planner=MagicMock(),
        validator=MagicMock(),
        executor=executor,
        cognitive_manager=MagicMock(),
        execution_policy=ExecutionPolicy(allow_destructive_from_core=True),
        default_tool_timeout=0.1,
    )
    try:
        task = Task(
            tool="file",
            action="delete",
            args={"path": str(target), "user_confirmed": True},
        )
        result = agent._process_task(task)

        assert result.status == TaskStatus.FAILED
        assert "requires user confirmation" in result.error.lower()
        assert not executor.called
        assert target.read_text(encoding="utf-8") == "preserve"
    finally:
        agent.close()
