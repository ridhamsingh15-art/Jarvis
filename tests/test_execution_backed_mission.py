from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


from tools.browser import BrowserTool


class ControlledFailingBrowserTool(BrowserTool):
    """Pickleable child-process browser fixture used to avoid real browser navigation."""

    def execute(self, action: str, args: dict) -> str:
        if action != "open_url":
            return super().execute(action, args)
        import os

        from core.exceptions import ExecutionError

        marker = os.environ.get("JARVIS_TEST_BROWSER_ATTEMPTS_FILE")
        if marker:
            with Path(marker).open("a", encoding="utf-8") as stream:
                stream.write("attempt\n")
        raise ExecutionError("controlled browser failure before navigation was accepted")



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

    # Task 3: destructive actions wait for a durable operator decision before execution.
    denied = _run("--mission", f"delete {workspace / 'file-00.txt'}", "--mission-db", str(db_path),
                  "--mission-id", "e2e-denied", "--workspace-root", str(workspace))
    assert denied.returncode == 1, denied.stdout + denied.stderr
    assert '"state": "WAITING_APPROVAL"' in denied.stdout
    assert (workspace / "file-00.txt").read_text(encoding="utf-8").startswith("REAL_CONTENT_MARKER_0")
    with sqlite3.connect(db_path) as db:
        state, reason = db.execute("SELECT state, failure_reason FROM missions WHERE id='e2e-denied'").fetchone()
        step = db.execute("SELECT status, exit_code, error FROM mission_steps WHERE mission_id='e2e-denied'").fetchone()
    assert state == "WAITING_APPROVAL" and "requires confirmation" in reason.lower()
    assert step[0] == "pending_approval" and step[1] is None and "confirmation" in step[2].lower()
    denied_decision = subprocess.run(
        [PYTHON, str(ROOT / "mission_crash_safe.py"), "--mission-db", str(db_path),
         "--workspace-root", str(workspace), "--deny", "e2e-denied", "--step", "1"],
        cwd=ROOT, capture_output=True, text=True, timeout=20, check=False,
    )
    assert denied_decision.returncode == 0, denied_decision.stdout + denied_decision.stderr
    assert "APPROVAL=DENIED" in denied_decision.stdout
    with sqlite3.connect(db_path) as db:
        state = db.execute("SELECT state FROM missions WHERE id='e2e-denied'").fetchone()[0]
        step = db.execute("SELECT status, exit_code FROM mission_steps WHERE mission_id='e2e-denied'").fetchone()
    assert state == "FAILED" and step[0] == "blocked" and step[1] == 126
    assert (workspace / "file-00.txt").read_text(encoding="utf-8").startswith("REAL_CONTENT_MARKER_0")

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


def test_interrupted_side_effect_requires_explicit_resolution(tmp_path: Path) -> None:
    from mission_control.mission import Mission, MissionState
    from mission_control.store import MissionStore

    db_path = tmp_path / "recovery-required.sqlite3"
    store = MissionStore(db_path)
    mission = Mission(
        id="unknown-outcome",
        objective="inspect files then summarize",
        state=MissionState.RUNNING,
        steps=[
            json.dumps({"tool": "file", "action": "list_largest_files", "args": {"path": str(tmp_path), "limit": 5}}),
            json.dumps({"tool": "file", "action": "summarize_files", "args": {"path": str(tmp_path), "limit": 5}}),
        ],
    )
    store.save_mission(mission)
    store.record_step("unknown-outcome", 0, {
        "tool": "file", "action": "list_largest_files", "args": {"path": str(tmp_path), "limit": 5},
        "status": "running", "stdout": "", "stderr": "", "exit_code": None,
        "error": "", "started_at": "2026-10-17T00:00:00+00:00",
    })

    recovered = store.load_mission("unknown-outcome")
    assert recovered is not None
    assert recovered.state is MissionState.RECOVERY_REQUIRED
    assert recovered.step_results[0]["status"] == "unknown"

    # Normal resume must stop and report the unknown outcome; it must not replay the step.
    blocked = _run("--resume", "--mission-db", str(db_path), "--mission-id", "unknown-outcome")
    assert blocked.returncode == 1, blocked.stdout + blocked.stderr
    assert '"state": "RECOVERY_REQUIRED"' in blocked.stdout

    # The operator explicitly confirms the postcondition was not achieved before retrying.
    retried = _run(
        "--resume", "--mission-db", str(db_path), "--mission-id", "unknown-outcome",
        "--resolve-interrupted-step", "retry",
    )
    assert retried.returncode == 0, retried.stdout + retried.stderr
    assert '"state": "COMPLETED"' in retried.stdout
    with sqlite3.connect(db_path) as db:
        state, completed = db.execute(
            "SELECT state, completed_json FROM missions WHERE id='unknown-outcome'"
        ).fetchone()
    assert state == "COMPLETED"
    assert len(json.loads(completed)) == 2


def test_interrupted_step_can_be_marked_completed_only_explicitly(tmp_path: Path) -> None:
    from mission_control.mission import Mission, MissionState
    from mission_control.store import MissionStore

    db_path = tmp_path / "recovery-completed.sqlite3"
    store = MissionStore(db_path)
    step = json.dumps({"tool": "file", "action": "list_largest_files", "args": {"path": str(tmp_path), "limit": 5}})
    mission = Mission(id="confirmed-complete", objective="list files", state=MissionState.RUNNING, steps=[step])
    store.save_mission(mission)
    store.record_step("confirmed-complete", 0, {
        "tool": "file", "action": "list_largest_files", "args": {"path": str(tmp_path), "limit": 5},
        "status": "running", "stdout": "", "stderr": "", "exit_code": None, "error": "",
    })

    recovered = store.load_mission("confirmed-complete")
    assert recovered is not None and recovered.state is MissionState.RECOVERY_REQUIRED
    resolved = store.resolve_interrupted_step("confirmed-complete", "completed")
    assert resolved.state is MissionState.COMPLETED
    assert resolved.completed_steps == [step]
    assert resolved.step_results[0]["status"] == "completed"


def test_autonomy_batch_executor_runs_one_real_mission_and_maps_results(monkeypatch) -> None:
    import asyncio

    from core.autonomy.mission_adapter import CrashSafeGoalStepExecutor
    from core.autonomy.models import Goal, GoalPlan, GoalStep
    from core.models.primitives import Identifier

    mission_steps = [
        json.dumps({"id": "discover", "tool": "file", "action": "list_directory", "args": {"path": "."}}),
        json.dumps({"id": "read", "tool": "file", "action": "read_file", "args": {"path": "README.md"}, "depends_on": ["discover"]}),
    ]
    goal = Goal(id=Identifier("goal_batch_test"), description="Inspect project", metadata={})
    plan = GoalPlan(goal_id=goal.id, steps=[
        GoalStep(
            id=Identifier("goal_batch_test_step_1"), description="discover",
            context={"tool": "file", "action": "list_directory", "args": {"path": "."},
                     "mission_steps": mission_steps, "plan_step_index": 0, "mission_id": "autonomy-goal_batch_test"},
        ),
        GoalStep(
            id=Identifier("goal_batch_test_step_2"), description="read",
            context={"tool": "file", "action": "read_file", "args": {"path": "README.md"},
                     "mission_steps": mission_steps, "plan_step_index": 1, "mission_id": "autonomy-goal_batch_test"},
        ),
    ])
    calls = []

    def fake_execute_objective(objective, *, mission_id, steps, tool_registry=None):
        calls.append((objective, mission_id, steps))
        return {
            "mission": {"state": "COMPLETED", "verification_status": "verified"},
            "steps": [
                {"step_index": 0, "tool": "file", "action": "list_directory", "status": "completed",
                 "result": {"files": ["README.md"]}, "paths": ["README.md"], "verification": {"status": "verified"}},
                {"step_index": 1, "tool": "file", "action": "read_file", "status": "completed",
                 "result": "hello", "paths": ["README.md"], "verification": {"status": "verified"}},
            ],
        }

    monkeypatch.setattr("mission_control.crash_cli.execute_objective", fake_execute_objective)
    results = asyncio.run(CrashSafeGoalStepExecutor().execute_plan(goal, plan))

    assert len(calls) == 1
    assert calls[0] == (goal.description, "autonomy-goal_batch_test", mission_steps)
    assert [item["action"] for item in results] == ["list_directory", "read_file"]
    assert all(item["verification_status"] == "verified" for item in results)


def test_autonomy_batch_executor_refuses_unverified_success(monkeypatch) -> None:
    import asyncio

    from core.autonomy.exceptions import GoalExecutionError
    from core.autonomy.mission_adapter import CrashSafeGoalStepExecutor
    from core.autonomy.models import Goal, GoalPlan, GoalStep
    from core.models.primitives import Identifier

    encoded = [json.dumps({"id": "one", "tool": "file", "action": "list_directory", "args": {"path": "."}})]
    goal = Goal(id=Identifier("goal_unverified_test"), description="Inspect project", metadata={})
    plan = GoalPlan(goal_id=goal.id, steps=[GoalStep(
        id=Identifier("goal_unverified_test_step_1"), description="inspect",
        context={"tool": "file", "action": "list_directory", "args": {"path": "."},
                 "mission_steps": encoded, "plan_step_index": 0, "mission_id": "autonomy-goal_unverified_test"},
    )])
    monkeypatch.setattr("mission_control.crash_cli.execute_objective", lambda *args, **kwargs: {
        "mission": {"state": "COMPLETED", "verification_status": "partial"},
        "steps": [{"step_index": 0, "tool": "file", "action": "list_directory", "status": "completed",
                   "result": {"files": []}, "paths": [], "verification": {"status": "partial"}}],
    })

    with pytest.raises(GoalExecutionError, match="verification=partial"):
        asyncio.run(CrashSafeGoalStepExecutor().execute_plan(goal, plan))
    assert goal.metadata["batch_partial_execution"] is True


def test_autonomous_goal_manager_executes_and_verifies_real_multi_step_mission(
    tmp_path: Path, monkeypatch,
) -> None:
    import asyncio
    from unittest.mock import MagicMock

    from core.autonomy import (
        AutonomousGoalManager,
        CrashSafeGoalStepExecutor,
        DAGGoalScheduler,
        DefaultGoalEvaluator,
        ExecutionBackedGoalPlanner,
        GoalState,
    )
    from core.autonomy.sqlite_persistence import SQLiteGoalPersistence
    from core.events.bus import EventBus

    workspace = tmp_path / "agent-workspace"
    workspace.mkdir()
    for index in range(12):
        (workspace / f"agent-file-{index:02}.txt").write_text(
            f"AGENT_E2E_MARKER_{index} " + ("data " * (index + 1)), encoding="utf-8"
        )
    monkeypatch.setenv("JARVIS_MISSION_DB", str(tmp_path / "agent-missions.sqlite3"))
    monkeypatch.setenv("JARVIS_MISSION_WORKSPACE_ROOT", str(workspace))

    async def scenario() -> None:
        logger = MagicMock()
        persistence = SQLiteGoalPersistence(tmp_path / "autonomy-goals.sqlite3")
        manager = AutonomousGoalManager(
            planner=ExecutionBackedGoalPlanner(),
            scheduler=DAGGoalScheduler(),
            persistence=persistence,
            evaluator=DefaultGoalEvaluator(),
            event_bus=EventBus(logger),
            logger=logger,
            step_executor=CrashSafeGoalStepExecutor(),
        )
        await manager.start()
        goal = manager.create_goal(
            f"List the 10 largest files in {workspace} and summarize them"
        )
        manager.start_goal(goal.id)
        for _ in range(200):
            state = manager.status(goal.id)
            if state in {GoalState.COMPLETED, GoalState.FAILED}:
                break
            await asyncio.sleep(0.05)

        saved = next(item for item in manager.list_goals() if item.id == goal.id)
        assert manager.status(goal.id) is GoalState.COMPLETED, saved.metadata.get("failure_reason")
        assert saved.metadata["verification_status"] == "verified"
        assert len(saved.metadata["execution_results"]) == 2
        assert [item["action"] for item in saved.metadata["execution_results"]] == [
            "list_largest_files", "summarize_files",
        ]
        assert all(item["verification_status"] == "verified" for item in saved.metadata["execution_results"])
        await manager.stop()

    asyncio.run(scenario())


def test_autonomy_batch_executor_surfaces_operator_approval_as_intervention(monkeypatch) -> None:
    import asyncio

    from core.autonomy.exceptions import GoalInterventionRequired
    from core.autonomy.mission_adapter import CrashSafeGoalStepExecutor
    from core.autonomy.models import Goal, GoalPlan, GoalStep
    from core.models.primitives import Identifier

    encoded = [json.dumps({"id": "one", "tool": "notes", "action": "search_notes", "args": {"query": "status"}})]
    goal = Goal(id=Identifier("goal_approval_test"), description="Search notes", metadata={})
    plan = GoalPlan(goal_id=goal.id, steps=[GoalStep(
        id=Identifier("goal_approval_test_step_1"), description="search",
        context={"tool": "notes", "action": "search_notes", "args": {"query": "status"},
                 "mission_steps": encoded, "plan_step_index": 0, "mission_id": "autonomy-goal_approval_test"},
    )])
    monkeypatch.setattr("mission_control.crash_cli.execute_objective", lambda *args, **kwargs: {
        "mission": {
            "state": "WAITING_APPROVAL",
            "verification_status": "not_verified",
            "failure_reason": "Execution policy requires confirmation for notes.search_notes",
        },
        "steps": [{
            "step_index": 0, "tool": "notes", "action": "search_notes",
            "status": "pending_approval", "result": None,
            "verification": {"status": "not_run"},
        }],
    })

    with pytest.raises(GoalInterventionRequired, match="WAITING_APPROVAL"):
        asyncio.run(CrashSafeGoalStepExecutor().execute_plan(goal, plan))


def test_real_autonomy_goal_replans_after_verified_read_only_failure(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    from unittest.mock import MagicMock

    from core.autonomy import (
        AutonomousGoalManager,
        DAGGoalScheduler,
        DefaultGoalEvaluator,
        ExecutionBackedGoalPlanner,
        GoalState,
    )
    from core.autonomy.mission_adapter import CrashSafeGoalStepExecutor
    from core.autonomy.sqlite_persistence import SQLiteGoalPersistence
    from core.events.bus import EventBus

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    expected = workspace / "known.txt"
    expected.write_text("RECOVERY_FINAL_STATE_MARKER", encoding="utf-8")
    missing = workspace / "missing.txt"
    mission_db = tmp_path / "crash-missions.sqlite3"
    monkeypatch.setenv("JARVIS_MISSION_DB", str(mission_db))
    monkeypatch.setenv("JARVIS_MISSION_WORKSPACE_ROOT", str(workspace))

    initial = [
        json.dumps({"id": "inspect", "tool": "file", "action": "list_directory",
                    "args": {"path": str(workspace)}, "depends_on": []}),
        json.dumps({"id": "read-missing", "tool": "file", "action": "read_file",
                    "args": {"path": str(missing)}, "depends_on": ["inspect"]}),
    ]
    replacement = [
        json.dumps({"id": "read-known", "tool": "file", "action": "read_file",
                    "args": {"path": str(expected)}, "depends_on": []}),
    ]

    class ControlledPlanner:
        def __init__(self):
            self.base = ExecutionBackedGoalPlanner()
            self.replan_calls = 0
        def create_plan(self, goal):
            return self.base._make_goal_plan(goal, initial, f"autonomy-{goal.id.value}")
        def replan_after_failure(self, goal, previous_plan, failure_reason):
            self.replan_calls += 1
            assert goal.metadata.get("safe_replan_allowed") is True
            assert goal.metadata.get("recovery_evidence")
            return self.base._make_goal_plan(
                goal, replacement, f"autonomy-{goal.id.value}-replan1",
            )

    async def scenario():
        logger = MagicMock()
        planner = ControlledPlanner()
        persistence = SQLiteGoalPersistence(tmp_path / "goals.sqlite3")
        manager = AutonomousGoalManager(
            planner=planner, scheduler=DAGGoalScheduler(), persistence=persistence,
            evaluator=DefaultGoalEvaluator(), event_bus=EventBus(logger), logger=logger,
            step_executor=CrashSafeGoalStepExecutor(),
        )
        await manager.start()
        try:
            goal = manager.create_goal("Inspect the workspace and read a known file")
            manager.start_goal(goal.id)
            for _ in range(200):
                if manager.status(goal.id) in {GoalState.COMPLETED, GoalState.FAILED}:
                    break
                await asyncio.sleep(0.05)
            saved = persistence.get_goal(goal.id)
            assert saved is not None
            assert saved.state is GoalState.COMPLETED, saved.metadata.get("failure_reason")
            assert saved.metadata["replan_attempts"] == 1
            assert planner.replan_calls == 1
            assert saved.metadata["verification_status"] == "verified"
            assert "RECOVERY_FINAL_STATE_MARKER" in saved.metadata["execution_results"][0]["output"]

            from mission_control.crash_store import CrashSafeMissionStore
            store = CrashSafeMissionStore(mission_db)
            old_mission = store.mission(f"autonomy-{goal.id.value}")
            new_mission = store.mission(f"autonomy-{goal.id.value}-replan1")
            assert old_mission and old_mission["state"] == "FAILED"
            assert new_mission and new_mission["state"] == "COMPLETED"
            final_step = store.step(f"autonomy-{goal.id.value}-replan1", 0)
            assert final_step and final_step["verification"]["status"] == "verified"
        finally:
            await manager.stop()

    asyncio.run(scenario())


def test_failure_across_file_and_browser_families_never_replays_uncertain_browser_action(
    tmp_path: Path, monkeypatch,
) -> None:
    import asyncio
    from unittest.mock import MagicMock

    from core.autonomy import (
        AutonomousGoalManager,
        DAGGoalScheduler,
        DefaultGoalEvaluator,
        ExecutionBackedGoalPlanner,
        GoalState,
    )
    from core.autonomy.mission_adapter import CrashSafeGoalStepExecutor
    from core.autonomy.sqlite_persistence import SQLiteGoalPersistence
    from core.events.bus import EventBus
    from core.registry import Registry

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "safe.txt").write_text("safe", encoding="utf-8")
    mission_db = tmp_path / "cross-family.sqlite3"
    monkeypatch.setenv("JARVIS_MISSION_DB", str(mission_db))
    monkeypatch.setenv("JARVIS_MISSION_WORKSPACE_ROOT", str(workspace))
    attempt_marker = tmp_path / "browser-attempts.txt"
    monkeypatch.setenv("JARVIS_TEST_BROWSER_ATTEMPTS_FILE", str(attempt_marker))
    registry = Registry()
    registry.register(ControlledFailingBrowserTool())
    initial = [
        json.dumps({"id": "inspect", "tool": "file", "action": "list_directory",
                    "args": {"path": str(workspace)}, "depends_on": []}),
        json.dumps({"id": "open", "tool": "browser", "action": "open_url",
                    "args": {"url": "https://example.com/"}, "depends_on": ["inspect"]}),
    ]

    class Planner:
        def __init__(self):
            self.base = ExecutionBackedGoalPlanner()
            self.replans = 0
        def create_plan(self, goal):
            return self.base._make_goal_plan(goal, initial, f"autonomy-{goal.id.value}")
        def replan_after_failure(self, goal, previous_plan, failure_reason):
            self.replans += 1
            return self.base._make_goal_plan(
                goal, [json.dumps({"id": "unsafe-replay", "tool": "browser", "action": "open_url",
                                   "args": {"url": "https://example.com/"}, "depends_on": []})],
                f"autonomy-{goal.id.value}-replan1",
            )

    async def scenario():
        logger = MagicMock()
        planner = Planner()
        persistence = SQLiteGoalPersistence(tmp_path / "goals.sqlite3")
        manager = AutonomousGoalManager(
            planner=planner, scheduler=DAGGoalScheduler(), persistence=persistence,
            evaluator=DefaultGoalEvaluator(), event_bus=EventBus(logger), logger=logger,
            step_executor=CrashSafeGoalStepExecutor(tool_registry=registry),
        )
        await manager.start()
        try:
            goal = manager.create_goal("Inspect directory and open a browser URL")
            manager.start_goal(goal.id)
            for _ in range(200):
                if manager.status(goal.id) in {GoalState.COMPLETED, GoalState.FAILED, GoalState.PAUSED}:
                    break
                await asyncio.sleep(0.05)
            saved = persistence.get_goal(goal.id)
            assert saved is not None
            assert saved.state is GoalState.PAUSED, saved.metadata.get("intervention_required")
            assert saved.metadata["execution_state_untrusted"] is True
            assert planner.replans == 0
            from mission_control.crash_store import CrashSafeMissionStore
            store = CrashSafeMissionStore(mission_db)
            first = store.step(f"autonomy-{goal.id.value}", 0)
            second = store.step(f"autonomy-{goal.id.value}", 1)
            assert first and first["status"] == "completed"
            assert first["verification"]["status"] == "verified"
            assert second and second["status"] == "needs_review" and second["side_effecting"] == 1
            assert store.mission(f"autonomy-{goal.id.value}-replan1") is None

            # Explicit resume must consult the same durable ledger. The terminal
            # side-effecting failure is not replayed merely because the user clicked Resume.
            manager.resume_goal(goal.id)
            for _ in range(100):
                if manager.status(goal.id) is GoalState.PAUSED:
                    break
                await asyncio.sleep(0.05)
            assert manager.status(goal.id) is GoalState.PAUSED
            assert attempt_marker.read_text(encoding="utf-8").splitlines() == ["attempt"]
            assert planner.replans == 0
        finally:
            await manager.stop()

    asyncio.run(scenario())
