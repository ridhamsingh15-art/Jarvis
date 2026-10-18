"""Process-kill acceptance tests for durable mission recovery stages."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from mission_control.crash_store import CrashSafeMissionStore

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _command(db: Path, mission_id: str, workspace: Path, step: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            PYTHON, str(ROOT / "mission_crash_safe.py"),
            "--steps-json", json.dumps([step], separators=(",", ":")),
            "--mission-id", mission_id, "--mission-db", str(db),
            "--workspace-root", str(workspace), "--require-verified",
        ],
        cwd=ROOT, text=True, capture_output=True, timeout=20, check=False,
    )


def test_kill_after_completed_step_persistence_does_not_replay_side_effect(tmp_path: Path) -> None:
    """A crash after step commit but before mission finalization must resume from the ledger."""
    db = tmp_path / "persisted.sqlite3"
    marker = tmp_path / "after-persist.marker"
    target = tmp_path / "created-once.txt"
    mission_id = "kill-after-persisted-step"
    step = {
        "tool": "file",
        "action": "create_file",
        "args": {"path": str(target), "content": "durable-side-effect\n"},
    }

    # The child executes the real handler, lets the runner persist the verified
    # completed-step record, then blocks in the post-persistence callback.
    child = r"""
import sys, time
from pathlib import Path
from core.execution_policy import ExecutionPolicy
from mission_control.crash_cli import _engine
from mission_control.crash_safe import CrashSafeMissionRunner
from mission_control.crash_store import CrashSafeMissionStore

db, workspace, marker, mission_id, step_json = sys.argv[1:]
step = __import__("json").loads(step_json)
steps = [__import__("json").dumps(step, ensure_ascii=False)]
def after_step(_mission_id, _index, record):
    if record.get("status") == "completed":
        p = Path(marker)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("persisted\n", encoding="utf-8")
        while True:
            time.sleep(1)
runner = CrashSafeMissionRunner(
    CrashSafeMissionStore(db), _engine(workspace),
    ExecutionPolicy(allow_destructive_from_core=True), after_step=after_step,
)
runner.run(mission_id, "Structured diagnostic mission", steps)
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    process = subprocess.Popen(
        [PYTHON, "-c", child, str(db), str(tmp_path), str(marker), mission_id, json.dumps(step)],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not marker.exists():
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                raise AssertionError(
                    f"child exited before persistence marker (code={process.returncode})\n{stdout}\n{stderr}"
                )
            time.sleep(0.05)
        assert marker.exists(), "timed out waiting for persisted-step marker"
        assert target.exists()
        store = CrashSafeMissionStore(db)
        saved_step = store.step(mission_id, 0)
        assert saved_step and saved_step["status"] == "completed"
        assert saved_step["attempt_count"] == 1
        process.kill()
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()

    resumed = _command(db, mission_id, tmp_path, step)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert "MISSION_STATE=COMPLETED" in resumed.stdout
    assert target.exists()
    final_store = CrashSafeMissionStore(db)
    final_mission = final_store.mission(mission_id)
    final_step = final_store.step(mission_id, 0)
    assert final_mission and final_mission["state"] == "COMPLETED"
    assert final_step and final_step["status"] == "completed"
    assert final_step["attempt_count"] == 1



def test_success_shaped_tool_result_without_real_side_effect_is_not_success(tmp_path: Path) -> None:
    """A handler's success status cannot substitute for independently observed state."""
    from core.execution_policy import ExecutionPolicy
    from core.task import Task
    from mission_control.crash_safe import CrashSafeMissionRunner
    from mission_control.crash_store import CrashSafeMissionStore

    target = tmp_path / "never-created.txt"
    db = tmp_path / "false-success.sqlite3"

    class SuccessShapedEngine:
        def execute(self, task: Task) -> Task:
            task.start()
            task.complete({"message": "created successfully", "path": str(target), "exit_code": 0})
            return task

    step = {
        "tool": "file",
        "action": "create_file",
        "args": {"path": str(target)},
    }
    store = CrashSafeMissionStore(db)
    result = CrashSafeMissionRunner(
        store, SuccessShapedEngine(), ExecutionPolicy(allow_destructive_from_core=True)
    ).run("false-success", "Structured diagnostic mission", [json.dumps(step)])

    assert not target.exists()
    assert result["mission"]["state"] == "FAILED"
    assert result["mission"]["verification_status"] != "verified"
    saved = store.step("false-success", 0)
    assert saved is not None
    assert saved["status"] in {"failed", "needs_review"}
    assert saved["verification"]["status"] != "verified"

def test_legacy_mission_executor_rejects_success_shaped_missing_file(tmp_path: Path) -> None:
    """The older MissionExecutor path must not complete on a handler's claim alone."""
    from core.execution_policy import ExecutionPolicy
    from core.task import Task
    from mission_control.execution import MissionExecutor
    from mission_control.mission import Mission, MissionState

    target = tmp_path / "legacy-missing.txt"

    class SuccessShapedEngine:
        def execute(self, task: Task) -> Task:
            task.start()
            task.complete({"message": "created successfully", "path": str(target), "exit_code": 0})
            return task

    step = json.dumps({
        "tool": "file",
        "action": "create_file",
        "args": {"path": str(target)},
    })
    mission = Mission(
        id="legacy-false-success",
        objective="create a file",
        state=MissionState.RUNNING,
        steps=[step],
    )
    MissionExecutor(
        execution_engine=SuccessShapedEngine(),
        policy=ExecutionPolicy(allow_destructive_from_core=True),
    ).step(mission)

    assert not target.exists()
    assert mission.state == MissionState.FAILED
    assert mission.completed_steps == []
    assert mission.step_results[0]["status"] in {"failed", "needs_review"}
    assert "not independently verified" in mission.failure_reason




def test_kill_after_write_ahead_intent_before_handler_does_not_replay(tmp_path: Path) -> None:
    """A durable started intent with no observed side effect is still uncertain after a crash."""
    db = tmp_path / "before-handler.sqlite3"
    marker = tmp_path / "before-handler.marker"
    target = tmp_path / "must-not-be-created.txt"
    mission_id = "kill-before-handler"
    step = {
        "tool": "file",
        "action": "create_file",
        "args": {"path": str(target)},
    }
    child = r"""
import sys, time, json
from pathlib import Path
from core.execution_policy import ExecutionPolicy
from mission_control.crash_cli import _engine
from mission_control.crash_safe import CrashSafeMissionRunner
from mission_control.crash_store import CrashSafeMissionStore

db, workspace, marker, mission_id, step_json = sys.argv[1:]
step = json.loads(step_json)
steps = [json.dumps(step, ensure_ascii=False)]
def before_execute(_mission_id, _index, _task):
    p = Path(marker)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("write_ahead_intent_persisted_handler_not_called\n", encoding="utf-8")
    while True:
        time.sleep(1)
runner = CrashSafeMissionRunner(
    CrashSafeMissionStore(db), _engine(workspace),
    ExecutionPolicy(allow_destructive_from_core=True), before_execute=before_execute,
)
runner.run(mission_id, "Structured diagnostic mission", steps)
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    process = subprocess.Popen(
        [PYTHON, "-c", child, str(db), str(tmp_path), str(marker), mission_id, json.dumps(step)],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not marker.exists():
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                raise AssertionError(
                    f"child exited before pre-handler marker (code={process.returncode})\n{stdout}\n{stderr}"
                )
            time.sleep(0.05)
        assert marker.exists(), "timed out waiting for write-ahead intent marker"
        assert not target.exists()
        before = CrashSafeMissionStore(db).step(mission_id, 0)
        assert before and before["status"] == "started" and before["attempt_count"] == 1
        process.kill()
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()

    resumed = _command(db, mission_id, tmp_path, step)
    assert resumed.returncode == 1, resumed.stdout + resumed.stderr
    assert "needs_review" in resumed.stdout
    assert not target.exists()
    final = CrashSafeMissionStore(db).step(mission_id, 0)
    assert final and final["status"] == "needs_review"
    assert final["attempt_count"] == 1



def test_legacy_mission_executor_never_replays_persisted_running_side_effect(tmp_path: Path) -> None:
    from core.execution_policy import ExecutionPolicy
    from core.task import Task
    from mission_control.execution import MissionExecutor
    from mission_control.mission import Mission, MissionState

    target = tmp_path / "legacy-maybe-created.txt"

    class RecordingEngine:
        calls = 0

        def execute(self, task: Task) -> Task:
            self.calls += 1
            task.start()
            target.write_text("would be duplicate side effect", encoding="utf-8")
            task.complete("created")
            return task

    engine = RecordingEngine()
    step = json.dumps({
        "tool": "file",
        "action": "create_file",
        "args": {"path": str(target), "text": "once"},
    })
    mission = Mission(
        id="legacy-interrupted-side-effect",
        objective="recover a legacy mission",
        state=MissionState.RUNNING,
        steps=[step],
        step_results=[{
            "step_index": 0,
            "tool": "file",
            "action": "create_file",
            "args": {"path": str(target), "text": "once"},
            "status": "running",
        }],
    )
    MissionExecutor(
        execution_engine=engine,
        policy=ExecutionPolicy(allow_destructive_from_core=True),
    ).step(mission)

    assert engine.calls == 0
    assert not target.exists()
    assert mission.state == MissionState.FAILED
    assert mission.step_results[0]["status"] == "needs_review"
    assert "outcome unknown" in mission.failure_reason.lower()
