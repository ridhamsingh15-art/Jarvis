import asyncio
from unittest.mock import MagicMock

import pytest

from core.autonomy import (
    AutonomousGoalManager,
    DAGGoalScheduler,
    DefaultGoalEvaluator,
    DefaultGoalPlanner,
    ExponentialBackoffPolicy,
    GoalPlan,
    GoalState,
    GoalStep,
    InMemoryGoalPersistence,
    LinearRetryPolicy,
    SchedulingError,
)
from core.events.bus import EventBus
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState


@pytest.fixture
def planner():
    return DefaultGoalPlanner()

@pytest.fixture
def scheduler():
    return DAGGoalScheduler()

@pytest.fixture
def persistence():
    return InMemoryGoalPersistence()

@pytest.fixture
def evaluator():
    return DefaultGoalEvaluator()

@pytest.fixture
def manager(planner, scheduler, persistence, evaluator):
    logger = MagicMock()
    event_bus = EventBus(logger)
    return AutonomousGoalManager(
        planner=planner,
        scheduler=scheduler,
        persistence=persistence,
        evaluator=evaluator,
        event_bus=event_bus,
        logger=logger
    )

def test_dag_scheduler_valid(scheduler):
    s1 = Identifier("s1")
    s2 = Identifier("s2")
    s3 = Identifier("s3")
    
    plan = GoalPlan(
        goal_id=Identifier("g1"),
        steps=[
            GoalStep(id=s1, description="step 1"),
            GoalStep(id=s2, description="step 2", dependencies=[s1]),
            GoalStep(id=s3, description="step 3", dependencies=[s1, s2])
        ]
    )
    
    waves = scheduler.schedule(plan)
    assert len(waves) == 3
    assert waves[0][0].id == s1
    assert waves[1][0].id == s2
    assert waves[2][0].id == s3

def test_dag_scheduler_cyclic(scheduler):
    s1 = Identifier("s1")
    s2 = Identifier("s2")
    
    plan = GoalPlan(
        goal_id=Identifier("g1"),
        steps=[
            GoalStep(id=s1, description="step 1", dependencies=[s2]),
            GoalStep(id=s2, description="step 2", dependencies=[s1])
        ]
    )
    
    with pytest.raises(SchedulingError):
        scheduler.schedule(plan)

def test_retry_policies():
    linear = LinearRetryPolicy()
    assert linear.get_delay(2) == 4.0
    
    exp = ExponentialBackoffPolicy()
    assert exp.get_delay(3) == 8.0

@pytest.mark.asyncio
async def test_manager_lifecycle(manager):
    assert manager.state == ComponentState.INITIALIZED
    await manager.start()
    assert manager.state == ComponentState.RUNNING
    await manager.stop()
    assert manager.state == ComponentState.STOPPED

@pytest.mark.asyncio
async def test_goal_execution_lifecycle(manager):
    await manager.start()
    
    goal = manager.create_goal("Build a test app")
    assert goal.state == GoalState.CREATED
    
    manager.start_goal(goal.id)
    assert manager.status(goal.id) == GoalState.RUNNING
    
    # Wait for mock execution to complete
    await asyncio.sleep(0.1)
    
    assert manager.status(goal.id) == GoalState.COMPLETED
    
    await manager.stop()

@pytest.mark.asyncio
async def test_goal_pause_resume(manager):
    await manager.start()
    
    goal = manager.create_goal("Long running goal")
    manager.start_goal(goal.id)
    assert manager.status(goal.id) == GoalState.RUNNING
    
    manager.pause_goal(goal.id)
    assert manager.status(goal.id) == GoalState.PAUSED
    
    manager.resume_goal(goal.id)
    assert manager.status(goal.id) == GoalState.RUNNING
    
    await asyncio.sleep(0.1)
    
    assert manager.status(goal.id) == GoalState.COMPLETED
    
    await manager.stop()
