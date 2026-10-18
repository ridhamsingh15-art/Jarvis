from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from mission_control.crash_store import CrashSafeMissionStore
from tools.shell import ShellTool

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _mission(db: Path, workspace: Path, mission_id: str, step: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(ROOT / "mission_crash_safe.py"), "--steps-json", json.dumps([step]),
         "--mission-id", mission_id, "--mission-db", str(db), "--workspace-root", str(workspace)],
        cwd=ROOT, capture_output=True, text=True, timeout=20, check=False,
    )


def _case_commands(target: Path, empty: Path) -> list[tuple[str, str]]:
    encoded = base64.b64encode(f"Remove-Item -Recurse -Force '{target}'".encode("utf-16le")).decode("ascii")
    return [
        ("powershell_long_flags", f'Remove-Item -Recurse -Force "{target}"'),
        ("powershell_short_flags", f'Remove-Item -r -fo "{target}"'),
        ("del_s_q", f'del /s /q "{target}\\*"'),
        ("rd_s_q", f'rd /s /q "{target}"'),
        ("rmdir_s_q", f'rmdir /s /q "{target}"'),
        ("robocopy_mir", f'robocopy "{empty}" "{target}" /mir'),
        ("robocopy_purge", f'robocopy "{empty}" "{target}" /purge'),
        ("python_shutil_rmtree", f'python -c "import shutil; shutil.rmtree(r\'{target}\')"'),
        ("python_os_remove", f'python -c "import os; os.remove(r\'{target / "sentinel.txt"}\')"'),
        ("powershell_encoded_delete", f'powershell -EncodedCommand {encoded}'),
        ("chained_delete", f'echo ok && del /s /q "{target}\\*"'),
        ("environment_expansion", 'del /s /q "%JARVIS_GATE_TARGET%\\*"'),
        ("whole_command_quoted", f'"Remove-Item -Recurse -Force \'{target}\'"'),
    ]


@pytest.mark.parametrize("case_index", range(13))
def test_shell_destructive_gate_matrix_is_denied_and_recorded(tmp_path: Path, monkeypatch, case_index: int) -> None:
    temp_root = Path(os.environ["TEMP"]).resolve()
    assert tmp_path.resolve().is_relative_to(temp_root), "policy matrix must only use a throwaway TEMP directory"
    target = tmp_path / "target"
    empty = tmp_path / "empty"
    target.mkdir()
    empty.mkdir()
    sentinel = target / "sentinel.txt"
    sentinel.write_text("must survive", encoding="utf-8")
    monkeypatch.setenv("JARVIS_GATE_TARGET", str(target))
    cases = _case_commands(target, empty)
    name, command = cases[case_index]

    # First exercise the actual ShellTool, not a mocked policy predicate.
    shell_result = ShellTool(workspace_root=tmp_path, timeout_seconds=5).run(command, cwd_override=str(tmp_path), timeout=5)
    shell_denied = shell_result.blocked
    shell_reason = shell_result.blocked_reason

    # Recreate the sample after the direct probe if it exposed a hole; every
    # command remains confined to this test's disposable directory.
    target.mkdir(exist_ok=True)
    sentinel.write_text("must survive", encoding="utf-8")
    db = tmp_path / f"{name}.sqlite3"
    step = {"tool": "shell", "action": "run", "args": {"command": command, "cwd": str(tmp_path), "timeout": 5}}
    result = _mission(db, tmp_path, "gate-" + name, step)
    recorded = CrashSafeMissionStore(db).step("gate-" + name, 0)
    assert shell_denied, f"GATE_HOLE={name}: real ShellTool did not deny; reason={shell_reason!r}; return_code={shell_result.return_code}"
    assert result.returncode == 1, result.stdout + result.stderr
    assert recorded and recorded["status"] == "blocked", f"GATE_HOLE={name}: no durable denial record: {recorded}"
    assert "high-risk shell command" in recorded["error"].lower(), recorded["error"]
    assert target.is_dir() and sentinel.read_text(encoding="utf-8") == "must survive", f"GATE_HOLE={name}: sample data changed"
    print(f"GATE_CASE={name} RESULT=DENIED RECORDED=true FILES_PRESERVED=true")


def test_file_tool_delete_route_is_denied_and_recorded(tmp_path: Path) -> None:
    temp_root = Path(os.environ["TEMP"]).resolve()
    assert tmp_path.resolve().is_relative_to(temp_root), "file-tool gate test must only use a throwaway TEMP directory"
    sentinel = tmp_path / "file-tool-sentinel.txt"
    sentinel.write_text("must survive", encoding="utf-8")
    db = tmp_path / "file-tool.sqlite3"
    step = {"tool": "file", "action": "delete", "args": {"path": str(sentinel)}}
    result = _mission(db, tmp_path, "gate-file-delete", step)
    record = CrashSafeMissionStore(db).step("gate-file-delete", 0)
    assert result.returncode == 1, result.stdout + result.stderr
    assert record and record["status"] == "pending_approval" and "requires confirmation" in record["error"].lower()
    assert sentinel.read_text(encoding="utf-8") == "must survive"
    denied = subprocess.run(
        [PYTHON, str(ROOT / "mission_crash_safe.py"), "--mission-db", str(db),
         "--deny", "gate-file-delete", "--step", "1", "--workspace-root", str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True, timeout=20, check=False,
    )
    assert denied.returncode == 0, denied.stdout + denied.stderr
    assert "APPROVAL=DENIED" in denied.stdout
    assert sentinel.read_text(encoding="utf-8") == "must survive"
    print("GATE_CASE=file.delete RESULT=DENIED_BY_OPERATOR RECORDED=true FILES_PRESERVED=true")
