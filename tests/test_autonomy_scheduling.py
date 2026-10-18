from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from core.autonomy.scheduling import SQLiteScheduleStore


def test_schedule_store_persists_pause_resume_and_run_history(tmp_path):
    db = tmp_path / "autonomy.sqlite3"
    store = SQLiteScheduleStore(db)
    due = datetime.now(timezone.utc) - timedelta(seconds=5)
    schedule = store.create("Check the project status", 300, first_run_at=due)

    reloaded = SQLiteScheduleStore(db)
    loaded = reloaded.get(schedule.schedule_id)
    assert loaded is not None
    assert loaded.description == schedule.description
    assert loaded.enabled is True

    paused = reloaded.set_enabled(schedule.schedule_id, False)
    assert paused.enabled is False
    assert reloaded.claim_due(now=datetime.now(timezone.utc)) == []

    resumed = reloaded.set_enabled(schedule.schedule_id, True)
    assert resumed.enabled is True
    claimed = reloaded.claim_due(now=datetime.now(timezone.utc))
    assert len(claimed) == 1
    assert claimed[0].status == "PENDING"
    assert claimed[0].goal_id.startswith("scheduled_")

    # Atomic claim/ledger prevents duplicate run records even with repeated polls.
    assert reloaded.claim_due(now=datetime.now(timezone.utc)) == []
    reloaded.update_run(claimed[0].run_id, "RUNNING")
    reloaded.update_run(claimed[0].run_id, "COMPLETED")
    assert reloaded.runs(schedule.schedule_id)[0].status == "COMPLETED"


def test_schedule_missed_intervals_do_not_catch_up_in_a_burst(tmp_path):
    store = SQLiteScheduleStore(tmp_path / "schedules.sqlite3")
    due = datetime.now(timezone.utc) - timedelta(days=2)
    schedule = store.create("One catch-up only", 600, first_run_at=due)
    now = datetime.now(timezone.utc)

    first = store.claim_due(now=now)
    assert len(first) == 1
    assert store.claim_due(now=now) == []
    updated = store.get(schedule.schedule_id)
    assert updated is not None
    assert datetime.fromisoformat(updated.next_run_at) > now


def test_schedule_validation_rejects_naive_time_and_too_short_interval(tmp_path):
    store = SQLiteScheduleStore(tmp_path / "schedules.sqlite3")
    try:
        store.create("too fast", 30)
    except ValueError as exc:
        assert "at least 60" in str(exc)
    else:
        raise AssertionError("interval under one minute should be rejected")

    try:
        store.create("naive timestamp", 60, first_run_at=datetime.fromisoformat("2026-01-01T00:00:00"))
    except ValueError as exc:
        assert "timezone-aware" in str(exc)
    else:
        raise AssertionError("naive timestamp should be rejected")


def test_manager_dispatches_due_schedule_as_a_durable_goal(tmp_path):
    from unittest.mock import MagicMock

    from core.autonomy import (
        AutonomousGoalManager,
        DAGGoalScheduler,
        DefaultGoalEvaluator,
        DefaultGoalPlanner,
        GoalState,
    )
    from core.autonomy.sqlite_persistence import SQLiteGoalPersistence
    from core.events.bus import EventBus
    from core.models.primitives import Identifier

    class ImmediateExecutor:
        async def execute(self, goal, step):
            return {"verification_status": "verified", "action": "test"}

    async def scenario():
        logger = MagicMock()
        persistence = SQLiteGoalPersistence(tmp_path / "manager.sqlite3")
        manager = AutonomousGoalManager(
            planner=DefaultGoalPlanner(),
            scheduler=DAGGoalScheduler(),
            persistence=persistence,
            evaluator=DefaultGoalEvaluator(),
            event_bus=EventBus(logger),
            logger=logger,
            step_executor=ImmediateExecutor(),
        )
        schedule = manager.create_schedule(
            "scheduled goal", 60,
            first_run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        await manager.start()
        try:
            for _ in range(100):
                runs = manager.list_schedule_runs(schedule.schedule_id)
                if runs and runs[0].status in {"COMPLETED", "FAILED", "PAUSED"}:
                    break
                await asyncio.sleep(0.05)
            runs = manager.list_schedule_runs(schedule.schedule_id)
            assert runs and runs[0].status == "COMPLETED"
            goal = persistence.get_goal(Identifier(runs[0].goal_id))
            assert goal is not None
            assert goal.description == "scheduled goal"
            assert goal.state is GoalState.COMPLETED
        finally:
            await manager.stop()

    asyncio.run(scenario())


def test_autonomy_service_owns_and_stops_background_event_loop():
    from core.autonomy.service import AutonomyService

    class FakeManager:
        started = False
        stopped = False
        async def start(self):
            self.started = True
        async def stop(self):
            self.stopped = True

    manager = FakeManager()
    service = AutonomyService(manager)
    service.start()
    assert service.running
    assert manager.started is True
    service.shutdown()
    assert manager.stopped is True
    assert service.running is False


def test_restart_pauses_interrupted_scheduled_goal_without_auto_resume(tmp_path):
    from unittest.mock import MagicMock

    import pytest

    from core.autonomy import (
        AutonomousGoalManager,
        DAGGoalScheduler,
        DefaultGoalEvaluator,
        DefaultGoalPlanner,
        GoalState,
    )
    from core.autonomy.sqlite_persistence import SQLiteGoalPersistence
    from core.events.bus import EventBus
    from core.models.primitives import Identifier

    db = tmp_path / "durable-restart.sqlite3"

    class BlockingExecutor:
        async def execute(self, goal, step):
            await asyncio.Event().wait()

    class NeverExecute:
        async def execute(self, goal, step):
            raise AssertionError("interrupted scheduled goal must not auto-resume after restart")

    def manager_for(logger, executor):
        persistence = SQLiteGoalPersistence(db)
        return AutonomousGoalManager(
            planner=DefaultGoalPlanner(), scheduler=DAGGoalScheduler(), persistence=persistence,
            evaluator=DefaultGoalEvaluator(), event_bus=EventBus(logger), logger=logger,
            step_executor=executor,
        )

    async def scenario():
        logger = MagicMock()
        first = manager_for(logger, BlockingExecutor())
        schedule = first.create_schedule(
            "Long scheduled task", 60,
            first_run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        await first.start()
        goal_id = None
        try:
            for _ in range(100):
                runs = first.list_schedule_runs(schedule.schedule_id)
                if runs and runs[0].status == "RUNNING":
                    goal_id = runs[0].goal_id
                    goal = first.status(Identifier(goal_id))
                    if goal == GoalState.RUNNING:
                        break
                await asyncio.sleep(0.05)
            assert goal_id is not None
            assert first.status(Identifier(goal_id)) is GoalState.RUNNING
        finally:
            await first.stop()

        second = manager_for(logger, NeverExecute())
        await second.start()
        try:
            assert second.status(Identifier(goal_id)) is GoalState.PAUSED
            recovered_goal = next(item for item in second.list_goals() if item.id.value == goal_id)
            assert recovered_goal.metadata["execution_state_untrusted"] is True
            assert recovered_goal.metadata["verification_status"] == "not_verified"
            from core.autonomy.exceptions import GoalExecutionError
            with pytest.raises(GoalExecutionError, match="execution state is untrusted"):
                second.resume_goal(Identifier(goal_id))
            assert second.status(Identifier(goal_id)) is GoalState.PAUSED
            runs = second.list_schedule_runs(schedule.schedule_id)
            assert runs and runs[0].status == "PAUSED"
            assert "reconciliation" in runs[0].error.lower()
        finally:
            await second.stop()

    asyncio.run(scenario())


def test_pending_schedule_dispatch_is_atomically_claimed_across_store_instances(tmp_path):
    path = tmp_path / "atomic-schedule.sqlite3"
    first = SQLiteScheduleStore(path)
    second = SQLiteScheduleStore(path)
    due = datetime.now(timezone.utc) - timedelta(seconds=2)
    first.create("single dispatch", 60, first_run_at=due)
    first.claim_due(now=datetime.now(timezone.utc))

    claimed_first = first.claim_pending_runs()
    claimed_second = second.claim_pending_runs()
    assert len(claimed_first) == 1
    assert claimed_first[0].status == "RUNNING"
    assert claimed_second == []
    assert second.run_for_goal(claimed_first[0].goal_id).status == "RUNNING"
