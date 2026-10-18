"""End-to-end acceptance tests across real JARVIS runtime boundaries.

These tests use subprocesses, real SQLite journals, and registered FileTool handlers.
They intentionally avoid mocking the executor or independent file postcondition checks.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

from core.autonomy import (
    AutonomousGoalManager,
    CrashSafeGoalStepExecutor,
    DAGGoalScheduler,
    DefaultGoalEvaluator,
    ExecutionBackedGoalPlanner,
    GoalState,
)
from core.autonomy.service import AutonomyService
from core.autonomy.sqlite_persistence import SQLiteGoalPersistence
from core.events.bus import EventBus

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _run_crash_safe(*args: str, timeout: float = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(ROOT / "mission_crash_safe.py"), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def test_real_verification_failure_blocks_dependent_file_mutation(tmp_path: Path) -> None:
    """A real postcondition mismatch must stop a later write through the CLI runtime."""
    source = tmp_path / "source.txt"
    source.write_text("OBSERVED_CONTENT_IS_DIFFERENT", encoding="utf-8")
    target = tmp_path / "must-not-exist.txt"
    db = tmp_path / "acceptance.sqlite3"
    steps = [
        {
            "id": "read-source",
            "tool": "file",
            "action": "read_file",
            "args": {"path": str(source)},
            "expected_outcome": f"file_contains:{source}::EXPECTED_CONTENT_THAT_IS_ABSENT",
        },
        {
            "id": "write-dependent",
            "tool": "file",
            "action": "write_file",
            "args": {"path": str(target), "content": "DEPENDENT_STEP_MUST_NOT_RUN"},
            "depends_on": ["read-source"],
        },
    ]

    result = _run_crash_safe(
        "--steps-json", json.dumps(steps),
        "--mission", "Verify source content before writing dependent output",
        "--mission-id", "real-verification-gate",
        "--mission-db", str(db),
        "--workspace-root", str(tmp_path),
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert not target.exists(), "dependent file mutation occurred after failed verification"
    from mission_control.crash_store import CrashSafeMissionStore

    store = CrashSafeMissionStore(db)
    mission = store.mission("real-verification-gate")
    first = store.step("real-verification-gate", 0)
    second = store.step("real-verification-gate", 1)
    assert mission is not None and mission["state"] == "FAILED"
    assert first is not None and first["status"] == "failed"
    assert first["verification"]["expected_outcome_status"] == "failed"
    assert second is None or second["status"] not in {"running", "completed"}
    print("REAL_VERIFICATION_GATE=PASS first_step=failed dependent_mutation=not_performed")


def test_real_autonomy_service_completes_goal_and_reloads_durable_state(
    tmp_path: Path, monkeypatch,
) -> None:
    """Exercise service thread -> goal manager -> planner -> crash-safe CLI -> real FileTool."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for index in range(5):
        (workspace / f"runtime-{index}.txt").write_text(
            f"RUNTIME_ACCEPTANCE_MARKER_{index} " + ("evidence " * (index + 1)),
            encoding="utf-8",
        )

    mission_db = tmp_path / "missions.sqlite3"
    goal_db = tmp_path / "goals.sqlite3"
    monkeypatch.setenv("JARVIS_MISSION_DB", str(mission_db))
    monkeypatch.setenv("JARVIS_MISSION_WORKSPACE_ROOT", str(workspace))

    def make_service() -> AutonomyService:
        logger = MagicMock()
        manager = AutonomousGoalManager(
            planner=ExecutionBackedGoalPlanner(),
            scheduler=DAGGoalScheduler(),
            persistence=SQLiteGoalPersistence(goal_db),
            evaluator=DefaultGoalEvaluator(),
            event_bus=EventBus(logger),
            logger=logger,
            step_executor=CrashSafeGoalStepExecutor(),
        )
        return AutonomyService(manager)

    service = make_service()
    service.start()
    goal = service.create_goal(
        f"List the 5 largest files in {workspace} and summarize them"
    )
    try:
        service.start_goal(goal.id)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if service.status(goal.id) in {GoalState.COMPLETED, GoalState.FAILED}:
                break
            time.sleep(0.05)

        assert service.status(goal.id) is GoalState.COMPLETED
        completed = next(item for item in service.list_goals() if item.id == goal.id)
        assert completed.metadata["verification_status"] == "verified"
        assert len(completed.metadata["execution_results"]) == 2
        assert all(
            item["verification_status"] == "verified"
            for item in completed.metadata["execution_results"]
        )
        assert "RUNTIME_ACCEPTANCE_MARKER_4" in json.dumps(
            completed.metadata["execution_results"], ensure_ascii=False
        )
    finally:
        service.shutdown()

    # A fresh service/manager instance must load the persisted terminal state, not rerun it.
    restarted = make_service()
    restarted.start()
    try:
        assert restarted.status(goal.id) is GoalState.COMPLETED
        reloaded = next(item for item in restarted.list_goals() if item.id == goal.id)
        assert reloaded.metadata["verification_status"] == "verified"
        assert len(reloaded.metadata["execution_results"]) == 2
    finally:
        restarted.shutdown()

    from mission_control.crash_store import CrashSafeMissionStore

    rows = CrashSafeMissionStore(mission_db).steps(f"autonomy-{goal.id.value}")
    assert len(rows) == 2
    assert all(row["status"] == "completed" and row["attempt_count"] == 1 for row in rows)
    print("REAL_AUTONOMY_SERVICE=PASS steps=2 verified=true restart=durable attempts=1")
