import asyncio
import builtins
import threading

from core.events.bus import EventBus
from core.models.domain import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport
from core.telemetry import AsyncLogger

from .enums import GoalPriority, GoalState
from .exceptions import GoalCreationError, GoalExecutionError
from .goals import GoalContext
from .interfaces import IGoalEvaluator, IGoalPersistence, IGoalPlanner, IGoalScheduler
from .models import Goal, GoalHistory


class AutonomousGoalManager(RuntimeComponent):
    """Orchestrates long-running persistent goal lifecycles."""

    def __init__(
        self,
        planner: IGoalPlanner,
        scheduler: IGoalScheduler,
        persistence: IGoalPersistence,
        evaluator: IGoalEvaluator,
        event_bus: EventBus,
        logger: AsyncLogger
    ) -> None:
        self._planner = planner
        self._scheduler = scheduler
        self._persistence = persistence
        self._evaluator = evaluator
        self._event_bus = event_bus
        self._logger = logger

        self._lock = threading.RLock()
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._active_contexts: dict[str, GoalContext] = {}

        self._state = ComponentState.INITIALIZED
        self._metadata = ComponentMetadata(
            id="core.autonomy",
            name="Autonomous Goal Manager",
            version="1.0.0",
            dependencies=["core.events", "core.telemetry"]
        )

    @property
    def metadata(self) -> ComponentMetadata:
        return self._metadata

    @property
    def state(self) -> ComponentState:
        return self._state

    async def start(self) -> None:
        if self._state in (ComponentState.STARTING, ComponentState.RUNNING):
            return

        self._state = ComponentState.STARTING
        self._logger.info("Starting Autonomous Goal Manager...")
        
        # Load running/queued goals from persistence in a real app here.
        
        self._state = ComponentState.RUNNING
        self._logger.info("Autonomous Goal Manager started.")

    async def stop(self) -> None:
        if self._state != ComponentState.RUNNING:
            return

        self._state = ComponentState.STOPPING
        self._logger.info("Stopping Autonomous Goal Manager...")
        
        # Cancel running background tasks cleanly
        for task in self._running_tasks.values():
            if not task.done():
                task.cancel()
                
        self._running_tasks.clear()
        
        self._state = ComponentState.STOPPED
        self._logger.info("Autonomous Goal Manager stopped.")

    async def health(self) -> HealthReport:
        try:
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.HEALTHY,
                details={"active_goals": len(self._active_contexts)}
            )
        except Exception as e:  # noqa: BLE001
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.UNHEALTHY,
                error=str(e)
            )

    def create_goal(self, description: str, priority: GoalPriority = GoalPriority.NORMAL) -> Goal:
        if not description:
            raise GoalCreationError("Description cannot be empty.")
            
        import uuid
        goal_id = Identifier(f"goal_{uuid.uuid4().hex[:8]}")
        goal = Goal(id=goal_id, description=description, priority=priority)
        
        self._persistence.save_goal(goal)
        self._publish_event("goal.created", {"goal_id": goal.id.value})
        
        return goal

    def start_goal(self, goal_id: Identifier) -> None:
        with self._lock:
            goal = self._persistence.get_goal(goal_id)
            if not goal:
                raise GoalExecutionError(f"Goal {goal_id.value} not found.")
                
            if goal.state not in (GoalState.CREATED, GoalState.QUEUED):
                raise GoalExecutionError(f"Cannot start goal in state {goal.state.value}.")
                
            ctx = GoalContext(goal)
            ctx.set_state(GoalState.RUNNING)
            self._active_contexts[goal_id.value] = ctx
            self._persistence.save_goal(ctx.goal)
            
            self._publish_event("goal.started", {"goal_id": goal_id.value})
            
            task = asyncio.create_task(self._execution_loop(goal_id))
            self._running_tasks[goal_id.value] = task

    def pause_goal(self, goal_id: Identifier) -> None:
        with self._lock:
            ctx = self._active_contexts.get(goal_id.value)
            if not ctx:
                raise GoalExecutionError(f"Goal {goal_id.value} is not active.")
                
            ctx.set_state(GoalState.PAUSED)
            self._persistence.save_goal(ctx.goal)
            
            # Cancel the background runner
            task = self._running_tasks.get(goal_id.value)
            if task and not task.done():
                task.cancel()

    def resume_goal(self, goal_id: Identifier) -> None:
        with self._lock:
            goal = self._persistence.get_goal(goal_id)
            if not goal or goal.state != GoalState.PAUSED:
                raise GoalExecutionError("Goal is not paused.")
                
            ctx = GoalContext(goal)
            ctx.set_state(GoalState.RUNNING)
            self._active_contexts[goal_id.value] = ctx
            self._persistence.save_goal(ctx.goal)
            
            self._publish_event("goal.started", {"goal_id": goal_id.value})
            
            task = asyncio.create_task(self._execution_loop(goal_id))
            self._running_tasks[goal_id.value] = task

    def cancel_goal(self, goal_id: Identifier) -> None:
        with self._lock:
            ctx = self._active_contexts.get(goal_id.value)
            if not ctx:
                # Might just be in DB but not active
                goal = self._persistence.get_goal(goal_id)
                if goal:
                    ctx = GoalContext(goal)
                else:
                    return
                    
            ctx.set_state(GoalState.CANCELLED)
            self._persistence.save_goal(ctx.goal)
            self._publish_event("goal.cancelled", {"goal_id": goal_id.value})
            
            task = self._running_tasks.get(goal_id.value)
            if task and not task.done():
                task.cancel()

    def status(self, goal_id: Identifier) -> GoalState | None:
        goal = self._persistence.get_goal(goal_id)
        return goal.state if goal else None

    def list_goals(self) -> builtins.list[Goal]:
        return self._persistence.list_goals()

    async def _execution_loop(self, goal_id: Identifier) -> None:
        try:
            ctx = self._active_contexts.get(goal_id.value)
            if not ctx:
                return

            plan = self._persistence.get_plan(goal_id)
            if not plan:
                plan = self._planner.create_plan(ctx.goal)
                self._persistence.save_plan(plan)

            waves = self._scheduler.schedule(plan)
            
            total_steps = len(plan.steps)
            completed_steps = 0
            
            for wave in waves:
                if ctx.goal.state != GoalState.RUNNING:
                    break
                    
                # Mock wave execution
                for step in wave:
                    await asyncio.sleep(0.01) # Mock execution
                    completed_steps += 1
                    
                self._publish_event("goal.progress", {
                    "goal_id": goal_id.value,
                    "percentage": str((completed_steps / total_steps) * 100)
                })
                
            if ctx.goal.state == GoalState.RUNNING:
                ctx.set_state(GoalState.COMPLETED)
                self._persistence.save_goal(ctx.goal)
                self._publish_event("goal.completed", {"goal_id": goal_id.value})
                
                # Run Evaluation
                eval_history = GoalHistory(goal_id=goal_id, logs=[])
                self._evaluator.evaluate(ctx.goal, eval_history)
                
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001
            ctx = self._active_contexts.get(goal_id.value)
            if ctx:
                ctx.set_state(GoalState.FAILED)
                self._persistence.save_goal(ctx.goal)
                self._publish_event("goal.failed", {"goal_id": goal_id.value})

    def _publish_event(self, topic: str, payload: dict[str, str]) -> None:
        event = Event(
            topic=topic,
            payload=payload,
            source=self.metadata.id
        )
        self._event_bus.publish(event)
