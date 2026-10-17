from __future__ import annotations

from core.autonomy import GoalPriority, GoalState, GoalStep, GoalPlan, SQLiteGoalPersistence
from core.models.primitives import Identifier
from core.autonomy.models import Goal


def test_goal_round_trip_preserves_enum_and_nested_types(tmp_path):
    store = SQLiteGoalPersistence(tmp_path / "autonomy.sqlite3")
    goal = Goal(
        id=Identifier("goal-roundtrip"),
        description="Build and test a small feature",
        state=GoalState.QUEUED,
        priority=GoalPriority.HIGH,
        metadata={"workspace": "sandbox", "tags": ["engineering"]},
    )
    store.save_goal(goal)

    loaded = store.get_goal(goal.id)
    assert loaded is not None
    assert loaded.id == goal.id
    assert loaded.state is GoalState.QUEUED
    assert loaded.priority is GoalPriority.HIGH
    assert loaded.metadata == goal.metadata
    assert store.get_goal(Identifier("missing")) is None


def test_plan_round_trip_preserves_step_types(tmp_path):
    store = SQLiteGoalPersistence(tmp_path / "autonomy.sqlite3")
    goal = Goal(id=Identifier("goal-plan"), description="Plan a feature")
    first = Identifier("step-one")
    second = Identifier("step-two")
    plan = GoalPlan(
        goal_id=goal.id,
        steps=[
            GoalStep(id=first, description="Inspect"),
            GoalStep(id=second, description="Implement", dependencies=[first]),
        ],
    )
    store.save_goal(goal)
    store.save_plan(plan)

    loaded = store.get_plan(goal.id)
    assert loaded is not None
    assert loaded.goal_id == goal.id
    assert loaded.steps[1].dependencies == [first]


def test_interrupted_work_is_paused_not_replayed(tmp_path):
    path = tmp_path / "autonomy.sqlite3"
    store = SQLiteGoalPersistence(path)
    goal = Goal(id=Identifier("goal-interrupted"), description="Potentially non-idempotent task", state=GoalState.RUNNING)
    store.save_goal(goal)

    restarted_store = SQLiteGoalPersistence(path)
    recovered = restarted_store.recover_interrupted_goals()

    assert len(recovered) == 1
    assert recovered[0].state is GoalState.PAUSED
    assert restarted_store.get_goal(goal.id).state is GoalState.PAUSED
    assert restarted_store.recover_interrupted_goals() == []


def test_plan_requires_existing_goal(tmp_path):
    from core.autonomy.exceptions import PersistenceError
    import pytest

    store = SQLiteGoalPersistence(tmp_path / "autonomy.sqlite3")
    with pytest.raises(PersistenceError, match="unknown goal"):
        store.save_plan(GoalPlan(goal_id=Identifier("missing"), steps=[]))


import pytest


@pytest.mark.asyncio
async def test_manager_startup_reconciles_interrupted_goals(tmp_path):
    import asyncio
    from unittest.mock import MagicMock

    from core.autonomy import AutonomousGoalManager, DAGGoalScheduler, DefaultGoalEvaluator, DefaultGoalPlanner
    from core.events.bus import EventBus

    store = SQLiteGoalPersistence(tmp_path / "autonomy.sqlite3")
    goal = Goal(id=Identifier("goal-recovery-manager"), description="Recover after restart", state=GoalState.RUNNING)
    store.save_goal(goal)
    logger = MagicMock()
    manager = AutonomousGoalManager(
        planner=DefaultGoalPlanner(),
        scheduler=DAGGoalScheduler(),
        persistence=store,
        evaluator=DefaultGoalEvaluator(),
        event_bus=EventBus(logger),
        logger=logger,
    )

    await manager.start()
    assert manager.status(goal.id) is GoalState.PAUSED
    logger.warning.assert_called_once()
    await manager.stop()
