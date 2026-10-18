from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from mission_control.crash_store import CrashSafeMissionStore

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _cli(db: Path, workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(ROOT / "mission_crash_safe.py"), "--mission-db", str(db),
         "--workspace-root", str(workspace), *args],
        cwd=ROOT, capture_output=True, text=True, timeout=20, check=False,
    )


def _create_review_case(db: Path, workspace: Path, mission_id: str) -> None:
    marker = workspace / f"{mission_id}.marker"
    step = {"tool": "shell", "action": "run", "args": {
        "command": "echo RETRY_OUTPUT", "cwd": str(workspace),
    }}
    process = subprocess.Popen(
        [PYTHON, str(ROOT / "mission_crash_safe.py"), "--steps-json", json.dumps([step]),
         "--mission-id", mission_id, "--mission-db", str(db), "--workspace-root", str(workspace),
         "--after-execute-marker", str(marker)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not marker.exists():
            if process.poll() is not None:
                out, err = process.communicate()
                raise AssertionError(f"mission exited before marker: {out}\n{err}")
            time.sleep(0.05)
        assert marker.exists(), "mission did not reach post-execute marker"
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
    step_record = store.step(mission_id, 0)
    assert step_record and step_record["status"] == "started"
    # A real restart recognizes the uncertain side effect and persists needs_review.
    restarted = _cli(db, workspace, "--steps-json", json.dumps([step]), "--mission-id", mission_id)
    assert restarted.returncode == 1, restarted.stdout + restarted.stderr
    assert "needs_review" in restarted.stdout
    assert store.step(mission_id, 0)["status"] == "needs_review"


def test_needs_review_list_show_and_abandon_end_to_end(tmp_path: Path) -> None:
    db = tmp_path / "review.sqlite3"
    mission_id = "review-abandon"
    _create_review_case(db, tmp_path, mission_id)

    listed = _cli(db, tmp_path, "--needs-review")
    assert listed.returncode == 0, listed.stdout + listed.stderr
    payload = json.loads(listed.stdout.split("NEEDS_REVIEW=", 1)[1])
    assert len(payload) == 1 and payload[0]["mission_id"] == mission_id
    assert "outcome is unknown" in payload[0]["review_reason"]

    shown = _cli(db, tmp_path, "--show-needs-review", mission_id)
    assert shown.returncode == 0, shown.stdout + shown.stderr
    detail = json.loads(shown.stdout.split("MISSION=", 1)[1])
    assert detail["steps"][0]["step_number"] == 1
    assert "outcome is unknown" in detail["steps"][0]["error"]

    abandoned = _cli(db, tmp_path, "--resolve-needs-review", mission_id, "--step", "1", "--resolution", "abandon")
    assert abandoned.returncode == 0, abandoned.stdout + abandoned.stderr
    assert "RESOLUTION=ABANDONED MISSION_STATE=ABANDONED" in abandoned.stdout
    store = CrashSafeMissionStore(db)
    assert store.mission(mission_id)["state"] == "ABANDONED"
    assert store.step(mission_id, 0)["status"] == "abandoned"
    assert "outcome is unknown" in store.step(mission_id, 0)["error"]
    # An abandoned mission is terminal; a later resume must not execute it again.
    resumed = _cli(db, tmp_path, "--mission-id", mission_id, "--resume")
    assert resumed.returncode == 1
    assert CrashSafeMissionStore(db).mission(mission_id)["state"] == "ABANDONED"
    assert CrashSafeMissionStore(db).step(mission_id, 0)["status"] == "abandoned"


def test_needs_review_retry_replays_only_after_explicit_operator_choice(tmp_path: Path) -> None:
    db = tmp_path / "retry.sqlite3"
    mission_id = "review-retry"
    _create_review_case(db, tmp_path, mission_id)

    resolved = _cli(db, tmp_path, "--resolve-needs-review", mission_id, "--step", "1", "--resolution", "retry")
    assert resolved.returncode == 0, resolved.stdout + resolved.stderr
    assert "RESOLUTION=RETRY MISSION_STATE=COMPLETED" in resolved.stdout
    assert "RETRY_OUTPUT" in resolved.stdout
    step = CrashSafeMissionStore(db).step(mission_id, 0)
    assert step and step["status"] == "completed" and step["attempt_count"] == 2
