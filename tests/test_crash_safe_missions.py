from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from mission_control.crash_store import CrashSafeMissionStore

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([PYTHON, str(ROOT / "mission_crash_safe.py"), *args], cwd=ROOT, text=True, capture_output=True, timeout=20, check=False)


def _args(db: Path, mission_id: str, workspace: Path, steps: list[dict], *extra: str) -> list[str]:
    return ["--steps-json", json.dumps(steps, separators=(",", ":")), "--mission-id", mission_id,
            "--mission-db", str(db), "--workspace-root", str(workspace), *extra]


def _wait_for(path: Path, process: subprocess.Popen[str], timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size:
            return
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(f"mission exited before marker appeared (code={process.returncode})\n{stdout}\n{stderr}")
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for real tool marker: {path}")


def _start(args: list[str]) -> subprocess.Popen[str]:
    return subprocess.Popen([PYTHON, str(ROOT / "mission_crash_safe.py"), *args], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def test_kill_after_real_side_effect_before_result_persistence_never_replays(tmp_path: Path) -> None:
    target, marker, db = tmp_path / "append.log", tmp_path / "after-tool.marker", tmp_path / "mission.sqlite3"
    steps = [{"tool": "file", "action": "append_line", "args": {"path": str(target), "line": "exactly-once"}, "user_confirmed": True}]
    process = _start(_args(db, "kill-after-side-effect", tmp_path, steps, "--after-execute-marker", str(marker)))
    try:
        _wait_for(marker, process)
        assert target.read_text(encoding="utf-8").splitlines() == ["exactly-once"]
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

    restarted = _command(*_args(db, "kill-after-side-effect", tmp_path, steps))
    assert restarted.returncode == 1, restarted.stdout + restarted.stderr
    assert "needs_review" in restarted.stdout
    assert target.read_text(encoding="utf-8").splitlines() == ["exactly-once"]
    store = CrashSafeMissionStore(db)
    mission, step = store.mission("kill-after-side-effect"), store.step("kill-after-side-effect", 0)
    assert mission and mission["state"] == "FAILED"
    assert step and step["status"] == "needs_review" and step["attempt_count"] == 1
    assert "outcome is unknown" in step["error"] and step["idempotency_key"]
    print("KILL_AFTER_SIDE_EFFECT=PASS status=needs_review file_lines=1 attempts=1")


def test_kill_during_long_running_shell_step_flags_unknown_outcome(tmp_path: Path) -> None:
    db, launches = tmp_path / "long.sqlite3", tmp_path / "launches.txt"
    command = "python -c \"import os,time;open('launches.txt','a').write(str(os.getpid())+chr(10));time.sleep(60)\""
    steps = [{"tool": "shell", "action": "run", "args": {"command": command, "cwd": str(tmp_path), "timeout": 90}}]
    process = _start(_args(db, "kill-during-shell", tmp_path, steps))
    child_pid = None
    try:
        _wait_for(launches, process)
        lines = launches.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        child_pid = int(lines[0])
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
        if child_pid:
            try:
                os.kill(child_pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                pass

    restarted = _command(*_args(db, "kill-during-shell", tmp_path, steps))
    assert restarted.returncode == 1, restarted.stdout + restarted.stderr
    assert "needs_review" in restarted.stdout
    assert len(launches.read_text(encoding="utf-8").splitlines()) == 1
    step = CrashSafeMissionStore(db).step("kill-during-shell", 0)
    assert step and step["status"] == "needs_review" and step["attempt_count"] == 1
    assert step["exit_code"] is None and step["normalized_code"] is None
    print("KILL_DURING_LONG_SHELL=PASS status=needs_review launches=1 attempts=1")


def test_shell_step_persists_real_os_exit_code_not_normalized_code(tmp_path: Path) -> None:
    db = tmp_path / "exit-code.sqlite3"
    steps = [{"tool": "shell", "action": "run", "args": {"command": "python -c \"import sys;print('REAL_OS_OUTPUT');sys.exit(7)\"", "cwd": str(tmp_path)}}]
    result = _command(*_args(db, "real-exit-code", tmp_path, steps))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "REAL_OS_OUTPUT" in result.stdout
    step = CrashSafeMissionStore(db).step("real-exit-code", 0)
    assert step and step["status"] == "failed" and step["exit_code"] == 7
    assert step["normalized_code"] is None
    print("SHELL_OS_EXIT_CODE=PASS exit_code=7 normalized_code=None")


def test_kill_after_read_only_tool_result_retries_same_idempotency_key(tmp_path: Path) -> None:
    (tmp_path / "input.txt").write_text("read-only data", encoding="utf-8")
    marker, db = tmp_path / "after-read.marker", tmp_path / "read-only.sqlite3"
    steps = [{"tool": "file", "action": "list_directory", "args": {"path": str(tmp_path)}}]
    process = _start(_args(db, "read-only-recovery", tmp_path, steps, "--after-execute-marker", str(marker)))
    try:
        _wait_for(marker, process)
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

    store = CrashSafeMissionStore(db)
    before = store.step("read-only-recovery", 0)
    assert before and before["status"] == "started" and before["attempt_count"] == 1
    result = _command(*_args(db, "read-only-recovery", tmp_path, steps))
    assert result.returncode == 0, result.stdout + result.stderr
    after, mission = store.step("read-only-recovery", 0), store.mission("read-only-recovery")
    assert after and after["status"] == "completed" and after["attempt_count"] == 2
    assert after["idempotency_key"] == before["idempotency_key"]
    assert mission and mission["state"] == "COMPLETED"

def test_destructive_action_is_denied_and_persisted_without_mutation(tmp_path: Path) -> None:
    target, db = tmp_path / "keep.txt", tmp_path / "policy.sqlite3"
    target.write_text("must survive", encoding="utf-8")
    steps = [{"tool": "file", "action": "delete", "args": {"path": str(target)}}]
    result = _command(*_args(db, "deny-delete", tmp_path, steps))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "MISSION_STATE=FAILED" in result.stdout
    assert "Execution policy deny" in result.stdout
    assert target.read_text(encoding="utf-8") == "must survive"
    store = CrashSafeMissionStore(db)
    mission, step = store.mission("deny-delete"), store.step("deny-delete", 0)
    assert mission and mission["state"] == "FAILED"
    assert step and step["status"] == "blocked" and "Execution policy deny" in step["error"]
    print("DESTRUCTIVE_POLICY=PASS status=FAILED step=blocked file_unchanged=true")
