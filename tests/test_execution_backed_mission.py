from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _run(*args: str, timeout: float = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(ROOT / "main.py"), *args], cwd=ROOT,
        text=True, capture_output=True, timeout=timeout, check=False,
    )


def test_real_mission_execution_policy_persistence_and_restart(tmp_path: Path) -> None:
    workspace = tmp_path / "real-files"
    workspace.mkdir()
    for index in range(12):
        (workspace / f"file-{index:02}.txt").write_text(
            f"REAL_CONTENT_MARKER_{index} " + ("data " * (index + 1)), encoding="utf-8"
        )
    db_path = tmp_path / "missions.sqlite3"

    # Task 1 + 2: objective -> plan -> real FileTool through ExecutionEngine -> durable outputs.
    objective = f"List the 10 largest files in {workspace} and summarize them"
    first = _run("--mission", objective, "--mission-db", str(db_path), "--mission-id", "e2e-real")
    assert first.returncode == 0, first.stdout + first.stderr
    assert '"state": "COMPLETED"' in first.stdout
    assert '"action": "list_largest_files"' in first.stdout
    assert '"action": "summarize_files"' in first.stdout
    assert "REAL_CONTENT_MARKER_11" in first.stdout

    with sqlite3.connect(db_path) as db:
        mission = db.execute("SELECT state, completed_json, failure_reason FROM missions WHERE id='e2e-real'").fetchone()
        steps = db.execute(
            "SELECT action, status, stdout, stderr, exit_code, paths_json FROM mission_steps WHERE mission_id='e2e-real' ORDER BY step_index"
        ).fetchall()
    assert mission[0] == "COMPLETED"
    assert len(json.loads(mission[1])) == 2
    assert len(steps) == 2
    assert [step[0] for step in steps] == ["list_largest_files", "summarize_files"]
    assert all(step[1] == "completed" and step[4] == 0 for step in steps)
    assert all("file-11.txt" in step[2] and json.loads(step[5]) for step in steps)

    # Task 3: destructive action is denied by the existing policy before tool execution.
    denied = _run("--mission", f"delete {workspace / 'file-00.txt'}", "--mission-db", str(db_path), "--mission-id", "e2e-denied")
    assert denied.returncode == 1, denied.stdout + denied.stderr
    assert "Execution policy denied" in denied.stdout
    with sqlite3.connect(db_path) as db:
        state, reason = db.execute("SELECT state, failure_reason FROM missions WHERE id='e2e-denied'").fetchone()
        step = db.execute("SELECT status, exit_code, error FROM mission_steps WHERE mission_id='e2e-denied'").fetchone()
    assert state == "FAILED" and "Execution policy denied" in reason
    assert step[0] == "blocked" and step[1] == 126 and "denied" in step[2].lower()

    # Task 4: kill the real process after a persisted successful step; a new process resumes step 2.
    recovery_id = "e2e-restart"
    process = subprocess.Popen(
        [PYTHON, str(ROOT / "main.py"), "--mission", objective, "--mission-db", str(db_path),
         "--mission-id", recovery_id, "--pause-after-step", "1"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    captured: list[str] = []
    try:
        assert process.stdout is not None
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            line = process.stdout.readline()
            if line:
                captured.append(line)
                if "MISSION_CHECKPOINT_READY=1" in line:
                    break
            elif process.poll() is not None:
                break
        assert any("MISSION_CHECKPOINT_READY=1" in line for line in captured), "process never reached persisted checkpoint: " + "".join(captured)
        process.kill()
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if process.stdout:
            process.stdout.close()

    with sqlite3.connect(db_path) as db:
        completed_before_restart = json.loads(db.execute("SELECT completed_json FROM missions WHERE id=?", (recovery_id,)).fetchone()[0])
    assert len(completed_before_restart) == 1
    resumed = _run("--resume", "--mission-db", str(db_path), "--mission-id", recovery_id)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert '"state": "COMPLETED"' in resumed.stdout
    with sqlite3.connect(db_path) as db:
        final_state, completed = db.execute("SELECT state, completed_json FROM missions WHERE id=?", (recovery_id,)).fetchone()
    assert final_state == "COMPLETED" and len(json.loads(completed)) == 2

    # Task 5: a real tool failure is recorded with a nonzero exit code and a useful reason.
    missing_path = tmp_path / "does-not-exist"
    failed = _run("--mission", f"List the 10 largest files in {missing_path}", "--mission-db", str(db_path), "--mission-id", "e2e-missing")
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert '"state": "FAILED"' in failed.stdout
    with sqlite3.connect(db_path) as db:
        state, reason = db.execute("SELECT state, failure_reason FROM missions WHERE id='e2e-missing'").fetchone()
        step = db.execute("SELECT status, exit_code, stderr FROM mission_steps WHERE mission_id='e2e-missing'").fetchone()
    assert state == "FAILED" and "does not exist" in reason.lower()
    assert step[0] == "failed" and step[1] == 1 and "does not exist" in step[2].lower()
