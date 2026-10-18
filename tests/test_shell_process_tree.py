from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _process_is_alive(pid: int) -> bool:
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == 0x00000102  # WAIT_TIMEOUT
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def test_child_of_killed_shell_mission_does_not_outlive_parent(tmp_path: Path) -> None:
    if os.name != "nt":
        pytest.skip("Windows Job Object behavior is the target of this regression test")
    temp_root = Path(os.environ["TEMP"]).resolve()
    assert tmp_path.resolve().is_relative_to(temp_root), "process-tree test must stay under TEMP"

    pid_file = tmp_path / "child.pid"
    db = tmp_path / "mission.sqlite3"
    command = "python -c \"import os,time; open('child.pid','w').write(str(os.getpid())); time.sleep(60)\""
    step = {"tool": "shell", "action": "run", "args": {"command": command, "cwd": str(tmp_path), "timeout": 90}}
    plan_args = [PYTHON, str(ROOT / "mission_crash_safe.py"), "--steps-json", json.dumps([step]),
                 "--mission-id", "kill-shell-parent", "--mission-db", str(db), "--workspace-root", str(tmp_path)]
    pending = subprocess.run(plan_args, cwd=ROOT, capture_output=True, text=True, timeout=20, check=False)
    assert pending.returncode == 1, pending.stdout + pending.stderr
    assert "MISSION_STATE=WAITING_APPROVAL" in pending.stdout
    assert not pid_file.exists(), "unapproved shell command must not start a child process"

    parent = subprocess.Popen(
        [PYTHON, str(ROOT / "mission_crash_safe.py"), "--approve", "kill-shell-parent",
         "--step", "1", "--mission-db", str(db), "--workspace-root", str(tmp_path)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    child_pid = None
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not pid_file.exists():
            if parent.poll() is not None:
                out, err = parent.communicate()
                raise AssertionError(f"approved mission exited before child started: {out}\n{err}")
            time.sleep(0.05)
        assert pid_file.exists(), "approved real child process did not publish its PID"
        child_pid = int(pid_file.read_text(encoding="utf-8"))
        assert _process_is_alive(child_pid), "child already exited before parent kill"
        parent.kill()
        parent.wait(timeout=5)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _process_is_alive(child_pid):
            time.sleep(0.05)
        assert not _process_is_alive(child_pid), f"shell child PID {child_pid} survived killed mission parent"
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        if parent.stdout:
            parent.stdout.close()
        if parent.stderr:
            parent.stderr.close()
        # Deliberately do not kill the child in cleanup: survival must fail the assertion above.

    print("SHELL_CHILD_LIFETIME=PASS child_terminated_when_mission_parent_killed=true")