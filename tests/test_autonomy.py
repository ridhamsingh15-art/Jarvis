import asyncio
from unittest.mock import MagicMock

import pytest

from core.autonomy import (
    AutonomousGoalManager,
    DAGGoalScheduler,
    DefaultGoalEvaluator,
    DefaultGoalPlanner,
    ExponentialBackoffPolicy,
    GoalExecutionError,
    GoalInterventionRequired,
    GoalPlan,
    GoalState,
    GoalStep,
    InMemoryGoalPersistence,
    LinearRetryPolicy,
    SchedulingError,
    UnconfiguredGoalStepExecutor,
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

class SuccessfulStepExecutor:
    async def execute(self, goal, step):
        return {"verification_status": "verified", "step_id": step.id.value}


class SlowStepExecutor:
    async def execute(self, goal, step):
        await asyncio.sleep(0.05)
        return {"verification_status": "verified", "step_id": step.id.value}


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
        logger=logger,
        step_executor=SuccessfulStepExecutor(),
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
async def test_unconfigured_executor_fails_closed(manager):
    manager._step_executor = UnconfiguredGoalStepExecutor()
    await manager.start()
    goal = manager.create_goal("Must not fake success")
    manager.start_goal(goal.id)
    await asyncio.sleep(0.02)

    assert manager.status(goal.id) is GoalState.PAUSED
    failed_goal = next(item for item in manager.list_goals() if item.id == goal.id)
    assert "refusing to simulate success" in failed_goal.metadata["intervention_required"]
    assert failed_goal.metadata["execution_state_untrusted"] is True
    await manager.stop()


@pytest.mark.asyncio
async def test_operator_intervention_pauses_goal_instead_of_marking_it_failed(manager):
    class InterventionExecutor:
        async def execute(self, goal, step):
            raise GoalInterventionRequired("Mission WAITING_APPROVAL: explicit operator approval required")

    manager._step_executor = InterventionExecutor()
    await manager.start()
    goal = manager.create_goal("Pause for an approval gate")
    manager.start_goal(goal.id)
    await asyncio.sleep(0.05)

    assert manager.status(goal.id) is GoalState.PAUSED
    paused = next(item for item in manager.list_goals() if item.id == goal.id)
    assert "WAITING_APPROVAL" in paused.metadata["intervention_required"]
    assert "failure_reason" not in paused.metadata

    manager._step_executor = SuccessfulStepExecutor()
    manager.resume_goal(goal.id)
    await asyncio.sleep(0.1)
    assert manager.status(goal.id) is GoalState.COMPLETED
    await manager.stop()


@pytest.mark.asyncio
async def test_intervention_after_a_verified_step_blocks_generic_plan_replay(manager):
    class TwoStepPlanner:
        def create_plan(self, goal):
            return GoalPlan(goal_id=goal.id, steps=[
                GoalStep(id=Identifier("verified-first"), description="first step"),
                GoalStep(id=Identifier("approval-second"), description="approval-gated step", dependencies=[Identifier("verified-first")]),
            ])

    class FirstStepThenIntervention:
        calls = 0

        async def execute(self, goal, step):
            self.calls += 1
            if step.id.value == "approval-second":
                raise GoalInterventionRequired("explicit approval required")
            return {"verification_status": "verified", "step_id": step.id.value}

    executor = FirstStepThenIntervention()
    manager._planner = TwoStepPlanner()
    manager._step_executor = executor
    await manager.start()
    goal = manager.create_goal("Do not replay a completed generic step")
    manager.start_goal(goal.id)
    await asyncio.sleep(0.1)

    assert manager.status(goal.id) is GoalState.PAUSED
    saved = next(item for item in manager.list_goals() if item.id == goal.id)
    assert saved.metadata["execution_state_untrusted"] is True
    assert len(saved.metadata["execution_results"]) == 1
    with pytest.raises(GoalExecutionError, match="execution state is untrusted"):
        manager.resume_goal(goal.id)
    assert executor.calls == 2
    await manager.stop()


@pytest.mark.asyncio
async def test_batch_executor_runs_once_for_the_whole_goal_plan(manager):
    class TwoStepPlanner:
        def create_plan(self, goal):
            return GoalPlan(goal_id=goal.id, steps=[
                GoalStep(id=Identifier("batch-1"), description="first"),
                GoalStep(id=Identifier("batch-2"), description="second", dependencies=[Identifier("batch-1")]),
            ])

    class BatchExecutor:
        calls = 0

        async def execute_plan(self, goal, plan):
            self.calls += 1
            assert len(plan.steps) == 2
            return [
                {"tool": "file", "action": "list_directory", "verification_status": "verified"},
                {"tool": "file", "action": "read_file", "verification_status": "verified"},
            ]

        async def execute(self, goal, step):
            raise AssertionError("batch-capable executor must not execute the whole plan once per step")

    executor = BatchExecutor()
    manager._planner = TwoStepPlanner()
    manager._step_executor = executor
    await manager.start()
    goal = manager.create_goal("Run a two-step batch safely")
    manager.start_goal(goal.id)
    await asyncio.sleep(0.1)

    assert manager.status(goal.id) is GoalState.COMPLETED
    saved = next(item for item in manager.list_goals() if item.id == goal.id)
    assert len(saved.metadata["execution_results"]) == 2
    assert executor.calls == 1
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


@pytest.mark.asyncio
async def test_duplicate_start_is_rejected(manager):
    await manager.start()
    goal = manager.create_goal("Only run once")

    manager.start_goal(goal.id)
    with pytest.raises(GoalExecutionError, match="Cannot start goal in state RUNNING"):
        manager.start_goal(goal.id)

    await asyncio.sleep(0.1)
    assert manager.status(goal.id) is GoalState.COMPLETED
    await manager.stop()


@pytest.mark.asyncio
async def test_planner_failure_marks_goal_failed(manager):
    events = []
    manager._event_bus.subscribe("goal.failed", lambda event: events.append(event.topic))
    manager._planner.create_plan = MagicMock(side_effect=RuntimeError("planner failed"))

    await manager.start()
    goal = manager.create_goal("Fail during planning")
    manager.start_goal(goal.id)
    await asyncio.sleep(0.02)

    assert manager.status(goal.id) is GoalState.FAILED
    assert events == ["goal.failed"]
    await manager.stop()


@pytest.mark.asyncio
async def test_unverified_step_pauses_and_is_never_replanned(manager):
    class PlannerThatMustNotReplan:
        def create_plan(self, goal):
            return GoalPlan(goal_id=goal.id, steps=[GoalStep(id=Identifier("uncertain"), description="possibly side-effecting")])

        def replan_after_failure(self, goal, previous_plan, failure_reason):
            raise AssertionError("unverified outcome must not be replanned")

    class UnverifiedExecutor:
        calls = 0

        async def execute(self, goal, step):
            self.calls += 1
            return {"verification_status": "not_verified", "step_id": step.id.value}

    executor = UnverifiedExecutor()
    manager._planner = PlannerThatMustNotReplan()
    manager._step_executor = executor
    await manager.start()
    goal = manager.create_goal("Do not continue when outcome is unknown")
    manager.start_goal(goal.id)
    await asyncio.sleep(0.05)

    assert manager.status(goal.id) is GoalState.PAUSED
    saved = next(item for item in manager.list_goals() if item.id == goal.id)
    assert saved.metadata["execution_state_untrusted"] is True
    assert saved.metadata["verification_status"] == "not_verified"
    assert "intervention_required" in saved.metadata
    assert executor.calls == 1
    await manager.stop()


@pytest.mark.asyncio
async def test_manager_performs_at_most_one_bounded_replan(manager):
    class RecoverablePlanner:
        replan_calls = 0

        def create_plan(self, goal):
            return GoalPlan(goal_id=goal.id, steps=[GoalStep(id=Identifier("initial"), description="initial")])

        def replan_after_failure(self, goal, previous_plan, failure_reason):
            self.replan_calls += 1
            assert "transient" in failure_reason
            return GoalPlan(goal_id=goal.id, steps=[GoalStep(id=Identifier("replanned"), description="replanned")])

    class FailOnceExecutor:
        calls = 0

        async def execute(self, goal, step):
            self.calls += 1
            if self.calls == 1:
                raise GoalExecutionError("transient read-only failure")
            return {"verification_status": "verified"}

    planner = RecoverablePlanner()
    executor = FailOnceExecutor()
    manager._planner = planner
    manager._step_executor = executor
    await manager.start()
    goal = manager.create_goal("Recover a safe read-only task")
    # The adapter must explicitly attest replay safety; a transient exception
    # alone is not enough to infer that no side effect occurred.
    goal.metadata["safe_replan_allowed"] = True
    manager._persistence.save_goal(goal)
    manager.start_goal(goal.id)
    await asyncio.sleep(0.1)

    assert manager.status(goal.id) is GoalState.COMPLETED
    saved = next(item for item in manager.list_goals() if item.id == goal.id)
    assert saved.metadata["replan_attempts"] == 1
    assert saved.metadata["verification_status"] == "verified"
    assert planner.replan_calls == 1
    assert executor.calls == 2
    await manager.stop()


@pytest.mark.asyncio
async def test_stop_checkpoints_running_goal_and_same_manager_can_resume(manager):
    manager._step_executor = SlowStepExecutor()
    await manager.start()
    goal = manager.create_goal("Pause safely on shutdown")
    manager.start_goal(goal.id)
    await asyncio.sleep(0)

    await manager.stop()
    assert manager.status(goal.id) is GoalState.PAUSED
    assert manager._running_tasks == {}
    saved = next(item for item in manager.list_goals() if item.id == goal.id)
    assert saved.metadata["execution_state_untrusted"] is True

    await manager.start()
    with pytest.raises(GoalExecutionError, match="execution state is untrusted"):
        manager.resume_goal(goal.id)
    assert manager.status(goal.id) is GoalState.PAUSED
    await manager.stop()


@pytest.mark.parametrize(
    ("initial", "target"),
    [
        (GoalState.COMPLETED, GoalState.CANCELLED),
        (GoalState.COMPLETED, GoalState.FAILED),
        (GoalState.FAILED, GoalState.COMPLETED),
        (GoalState.FAILED, GoalState.CANCELLED),
        (GoalState.CANCELLED, GoalState.COMPLETED),
        (GoalState.CANCELLED, GoalState.FAILED),
    ],
)
def test_goal_context_rejects_transitions_between_terminal_states(initial, target):
    from core.autonomy.goals import GoalContext
    from core.autonomy.models import Goal

    context = GoalContext(
        Goal(id=Identifier("terminal-immutability"), description="isolated test", state=initial)
    )

    with pytest.raises(GoalExecutionError, match="Cannot transition from terminal state"):
        context.set_state(target)

    assert context.goal.state is initial


@pytest.mark.parametrize(
    "terminal",
    [GoalState.COMPLETED, GoalState.FAILED, GoalState.CANCELLED],
)
def test_goal_context_allows_idempotent_terminal_state_write(terminal):
    from core.autonomy.goals import GoalContext
    from core.autonomy.models import Goal

    original = Goal(id=Identifier("terminal-idempotent"), description="isolated test", state=terminal)
    context = GoalContext(original)
    context.set_state(terminal)

    assert context.goal is original
    assert context.goal.state is terminal
