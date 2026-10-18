import asyncio
import builtins
import threading
from concurrent.futures import Future as ConcurrentFuture

from core.events.bus import EventBus
from core.models.domain import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport
from core.telemetry import AsyncLogger

from .enums import GoalPriority, GoalState
from .exceptions import GoalCreationError, GoalExecutionError, GoalInterventionRequired
from .goals import GoalContext
from .interfaces import IGoalEvaluator, IGoalPersistence, IGoalPlanner, IGoalScheduler
from .models import Goal, GoalHistory, GoalPlan
from .scheduling import GoalSchedule, SQLiteScheduleStore
from .step_executor import IGoalStepExecutor, UnconfiguredGoalStepExecutor


class AutonomousGoalManager(RuntimeComponent):
    """Orchestrates long-running persistent goal lifecycles."""

    def __init__(
        self,
        planner: IGoalPlanner,
        scheduler: IGoalScheduler,
        persistence: IGoalPersistence,
        evaluator: IGoalEvaluator,
        event_bus: EventBus,
        logger: AsyncLogger,
        step_executor: IGoalStepExecutor | None = None,
    ) -> None:
        self._planner = planner
        self._scheduler = scheduler
        self._persistence = persistence
        self._evaluator = evaluator
        self._event_bus = event_bus
        self._logger = logger
        self._step_executor = step_executor or UnconfiguredGoalStepExecutor()
        persistence_path = getattr(persistence, "path", None)
        self._schedule_store = (
            SQLiteScheduleStore(persistence_path)
            if persistence_path is not None
            else None
        )
        self._schedule_task: asyncio.Task[None] | None = None

        self._lock = threading.RLock()
        self._running_tasks: dict[
            str, asyncio.Task[None] | ConcurrentFuture[None]
        ] = {}
        self._active_contexts: dict[str, GoalContext] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

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
        self._loop = asyncio.get_running_loop()
        self._logger.info("Starting Autonomous Goal Manager...")
        
        # Reconcile interrupted durable goals before accepting new work. Never replay
        # RUNNING work automatically: its last external side effect may be unknown.
        recover = getattr(self._persistence, "recover_interrupted_goals", None)
        if callable(recover):
            recovered = recover()
            if recovered:
                self._logger.warning(
                    "Recovered %d interrupted goal(s) as PAUSED; explicit resume required.",
                    len(recovered),
                )
        
        self._state = ComponentState.RUNNING
        if self._schedule_store is not None:
            # Reconcile schedule runs before dispatch: a prior RUNNING goal is
            # paused by goal persistence and must never be silently resumed.
            for run in self._schedule_store.runs(limit=1000):
                if run.status != "RUNNING":
                    continue
                goal = self._persistence.get_goal(Identifier(run.goal_id))
                if goal is None:
                    self._schedule_store.update_run(run.run_id, "PENDING", "No goal was persisted before restart; safe to dispatch.")
                elif goal.state == GoalState.COMPLETED:
                    self._schedule_store.update_run(run.run_id, "COMPLETED")
                elif goal.state == GoalState.FAILED:
                    self._schedule_store.update_run(run.run_id, "FAILED", goal.metadata.get("failure_reason", ""))
                elif goal.state == GoalState.CANCELLED:
                    self._schedule_store.update_run(run.run_id, "CANCELLED")
                elif goal.state in (GoalState.CREATED, GoalState.QUEUED):
                    self._schedule_store.update_run(run.run_id, "PENDING", "Goal was persisted but never started; safe dispatch retry.")
                else:
                    self._schedule_store.update_run(run.run_id, "PAUSED", "Interrupted run requires explicit operator reconciliation.")
            self._schedule_task = asyncio.create_task(self._schedule_loop(), name="jarvis-durable-schedules")
        self._logger.info("Autonomous Goal Manager started.")

    async def stop(self) -> None:
        if self._state != ComponentState.RUNNING:
            return

        self._state = ComponentState.STOPPING
        self._logger.info("Stopping Autonomous Goal Manager...")
        if self._schedule_task and not self._schedule_task.done():
            self._schedule_task.cancel()
            await asyncio.gather(self._schedule_task, return_exceptions=True)
        self._schedule_task = None

        # Checkpoint active work before cancellation. A later start must not leave
        # same-process goals stranded in RUNNING after their tasks were discarded.
        with self._lock:
            for goal_id, context in self._active_contexts.items():
                if context.goal.state != GoalState.RUNNING:
                    continue
                if context.goal.metadata.get("in_flight_step_id") or context.goal.metadata.get("in_flight_batch"):
                    context.goal.metadata["execution_state_untrusted"] = True
                    context.goal.metadata["verification_status"] = "not_verified"
                    context.goal.metadata["intervention_kind"] = "unknown_outcome"
                    context.goal.metadata["intervention_required"] = (
                        "Shutdown interrupted an in-flight action; reconcile its durable execution ledger before continuing."
                    )
                context.set_state(GoalState.PAUSED)
                try:
                    self._persistence.save_goal(context.goal)
                except Exception as exc:  # noqa: BLE001 - keep shutdown progressing
                    self._logger.error(
                        "Could not checkpoint goal %s during shutdown: %s",
                        goal_id,
                        exc,
                    )

            tasks = list(self._running_tasks.values())
            for task in tasks:
                if not task.done():
                    self._cancel_task(task)

        # Wrap thread-safe futures so shutdown awaits workers scheduled by callers
        # outside the runtime's event-loop thread as well as native asyncio tasks.
        awaitables = [
            asyncio.wrap_future(task) if isinstance(task, ConcurrentFuture) else task
            for task in tasks
        ]
        if awaitables:
            await asyncio.gather(*awaitables, return_exceptions=True)

        with self._lock:
            self._running_tasks.clear()

        if self._schedule_task and not self._schedule_task.done():
            self._schedule_task.cancel()
            await asyncio.gather(self._schedule_task, return_exceptions=True)
        self._schedule_task = None
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

    def create_goal(
        self,
        description: str,
        priority: GoalPriority = GoalPriority.NORMAL,
        *,
        goal_id: Identifier | None = None,
    ) -> Goal:
        if not description or not description.strip():
            raise GoalCreationError("Description cannot be empty.")

        import uuid
        goal_id = goal_id or Identifier(f"goal_{uuid.uuid4().hex[:8]}")
        existing = self._persistence.get_goal(goal_id)
        if existing is not None:
            if existing.description != description:
                raise GoalCreationError("Goal ID already exists with a different description.")
            return existing
        goal = Goal(id=goal_id, description=description.strip(), priority=priority)
        
        self._persistence.save_goal(goal)
        self._publish_event("goal.created", {"goal_id": goal.id.value})
        
        return goal

    def start_goal(self, goal_id: Identifier) -> None:
        with self._lock:
            if self._state != ComponentState.RUNNING:
                raise GoalExecutionError("Goal manager must be running before starting a goal.")
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
            
            self._running_tasks[goal_id.value] = self._schedule_execution(goal_id)

    def pause_goal(self, goal_id: Identifier) -> None:
        with self._lock:
            ctx = self._active_contexts.get(goal_id.value)
            if not ctx:
                raise GoalExecutionError(f"Goal {goal_id.value} is not active.")
                
            if ctx.goal.metadata.get("in_flight_step_id") or ctx.goal.metadata.get("in_flight_batch"):
                ctx.goal.metadata["execution_state_untrusted"] = True
                ctx.goal.metadata["verification_status"] = "not_verified"
                ctx.goal.metadata["intervention_kind"] = "unknown_outcome"
                ctx.goal.metadata["intervention_required"] = (
                    "Pause interrupted an in-flight action; reconcile its durable execution ledger before continuing."
                )
            ctx.set_state(GoalState.PAUSED)
            self._persistence.save_goal(ctx.goal)
            self._set_schedule_run_for_goal(goal_id.value, "PAUSED", "Paused by operator.")
            
            # Cancel the background runner
            task = self._running_tasks.get(goal_id.value)
            if task and not task.done():
                self._cancel_task(task)

    def resume_goal(self, goal_id: Identifier) -> None:
        with self._lock:
            if self._state != ComponentState.RUNNING:
                raise GoalExecutionError("Goal manager must be running before resuming a goal.")
            goal = self._persistence.get_goal(goal_id)
            if not goal or goal.state != GoalState.PAUSED:
                raise GoalExecutionError("Goal is not paused.")
                
            requires_reconciliation = bool(
                goal.metadata.get("execution_state_untrusted")
                or goal.metadata.get("in_flight_step_id")
                or goal.metadata.get("in_flight_batch")
                or goal.metadata.get("batch_partial_execution")
            )
            if requires_reconciliation and not callable(getattr(self._step_executor, "execute_plan", None)):
                raise GoalExecutionError(
                    "Goal execution state is untrusted. This executor has no durable reconciliation ledger; "
                    "refusing to replay it. Inspect and reconcile the real-world outcome first."
                )
            ctx = GoalContext(goal)
            ctx.goal.metadata.pop("intervention_required", None)
            ctx.goal.metadata.pop("intervention_kind", None)
            ctx.set_state(GoalState.RUNNING)
            self._active_contexts[goal_id.value] = ctx
            self._persistence.save_goal(ctx.goal)
            self._set_schedule_run_for_goal(goal_id.value, "RUNNING")
            
            self._publish_event("goal.started", {"goal_id": goal_id.value})
            
            self._running_tasks[goal_id.value] = self._schedule_execution(goal_id)

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
            self._set_schedule_run_for_goal(goal_id.value, "CANCELLED", "Cancelled by operator.")
            self._publish_event("goal.cancelled", {"goal_id": goal_id.value})
            
            task = self._running_tasks.get(goal_id.value)
            if task and not task.done():
                self._cancel_task(task)

    def status(self, goal_id: Identifier) -> GoalState | None:
        goal = self._persistence.get_goal(goal_id)
        return goal.state if goal else None

    def list_goals(self) -> builtins.list[Goal]:
        return self._persistence.list_goals()

    def get_plan(self, goal_id: Identifier) -> GoalPlan | None:
        return self._persistence.get_plan(goal_id)

    def create_schedule(
        self, description: str, interval_seconds: int, *, first_run_at=None,
    ) -> GoalSchedule:
        if self._schedule_store is None:
            raise GoalExecutionError("Durable schedules require SQLite goal persistence.")
        return self._schedule_store.create(
            description, interval_seconds, first_run_at=first_run_at,
        )

    def list_schedules(self) -> list[GoalSchedule]:
        if self._schedule_store is None:
            return []
        return self._schedule_store.list()

    def set_schedule_enabled(self, schedule_id: str, enabled: bool) -> GoalSchedule:
        if self._schedule_store is None:
            raise GoalExecutionError("Durable schedules require SQLite goal persistence.")
        return self._schedule_store.set_enabled(schedule_id, enabled)

    def delete_schedule(self, schedule_id: str) -> None:
        if self._schedule_store is None:
            raise GoalExecutionError("Durable schedules require SQLite goal persistence.")
        self._schedule_store.delete(schedule_id)

    def list_schedule_runs(self, schedule_id: str | None = None):
        if self._schedule_store is None:
            return []
        return self._schedule_store.runs(schedule_id)

    def _set_schedule_run_for_goal(self, goal_id: str, status: str, error: str = "") -> None:
        if self._schedule_store is None:
            return
        run = self._schedule_store.run_for_goal(goal_id)
        if run is not None and run.status not in {"COMPLETED", "FAILED", "CANCELLED"}:
            self._schedule_store.update_run(run.run_id, status, error)

    async def _schedule_loop(self) -> None:
        store = self._schedule_store
        if store is None:
            return
        while self._state == ComponentState.RUNNING:
            try:
                store.claim_due()
                for run in store.claim_pending_runs():
                    schedule = store.get(run.schedule_id)
                    if schedule is None or not schedule.enabled:
                        store.update_run(run.run_id, "PAUSED", "Schedule was disabled or removed before dispatch.")
                        continue
                    goal_id = Identifier(run.goal_id)
                    goal = self._persistence.get_goal(goal_id)
                    if goal is None:
                        goal = self.create_goal(schedule.description, goal_id=goal_id)
                    if goal.state in (GoalState.CREATED, GoalState.QUEUED):
                        try:
                            self.start_goal(goal.id)
                        except Exception as exc:
                            store.update_run(run.run_id, "PENDING", f"Dispatch will be retried: {exc}")
                            raise
                    elif goal.state == GoalState.COMPLETED:
                        store.update_run(run.run_id, "COMPLETED")
                    elif goal.state == GoalState.FAILED:
                        store.update_run(run.run_id, "FAILED", goal.metadata.get("failure_reason", ""))
                    elif goal.state == GoalState.CANCELLED:
                        store.update_run(run.run_id, "CANCELLED")
                    else:
                        # RUNNING/PAUSED/PLANNING/WAITING must never be auto-replayed.
                        store.update_run(run.run_id, "PAUSED", "Existing goal needs explicit recovery/resume.")
                for run in store.runs(limit=1000):
                    if run.status != "RUNNING":
                        continue
                    goal = self._persistence.get_goal(Identifier(run.goal_id))
                    if goal is None:
                        store.update_run(run.run_id, "PENDING", "Goal record missing; dispatch will be retried.")
                    elif goal.state == GoalState.COMPLETED:
                        store.update_run(run.run_id, "COMPLETED")
                    elif goal.state == GoalState.FAILED:
                        store.update_run(run.run_id, "FAILED", goal.metadata.get("failure_reason", ""))
                    elif goal.state == GoalState.CANCELLED:
                        store.update_run(run.run_id, "CANCELLED")
                    elif goal.state == GoalState.PAUSED:
                        store.update_run(run.run_id, "PAUSED", goal.metadata.get("intervention_required", "Operator resume required."))
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - background loop must remain observable and alive
                self._logger.error("Durable schedule loop error: %s", exc)
            await asyncio.sleep(2.0)

    def _schedule_execution(
        self, goal_id: Identifier
    ) -> asyncio.Task[None] | ConcurrentFuture[None]:
        """Schedule goal work on the manager's runtime loop from any caller thread."""
        loop = self._loop
        if loop is None or loop.is_closed() or not loop.is_running():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError as exc:
                raise GoalExecutionError(
                    "Goal manager must be started before a goal can be scheduled."
                ) from exc
            self._loop = loop

        try:
            caller_loop = asyncio.get_running_loop()
        except RuntimeError:
            caller_loop = None

        if caller_loop is loop:
            return loop.create_task(self._execution_loop(goal_id))
        return asyncio.run_coroutine_threadsafe(self._execution_loop(goal_id), loop)

    def _cancel_task(
        self, task: asyncio.Task[None] | ConcurrentFuture[None]
    ) -> None:
        if isinstance(task, ConcurrentFuture):
            task.cancel()
            return
        loop = task.get_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(task.cancel)
        else:
            task.cancel()

    async def _execution_loop(self, goal_id: Identifier) -> None:
        try:
            ctx = self._active_contexts.get(goal_id.value)
            if not ctx:
                return

            plan = self._persistence.get_plan(goal_id)
            if not plan:
                plan = self._planner.create_plan(ctx.goal)
                self._persistence.save_plan(plan)
            if not plan.steps:
                raise GoalExecutionError(
                    f"Planner returned an empty plan for goal {goal_id.value}; refusing to mark it complete."
                )

            while True:
                waves = self._scheduler.schedule(plan)
                total_steps = len(plan.steps)
                completed_steps = 0
                try:
                    execute_plan = getattr(self._step_executor, "execute_plan", None)
                    if callable(execute_plan):
                        # Batch-capable executors (such as Mission Control) own the
                        # durable step ledger and must execute the whole plan exactly
                        # once, then return evidence aligned to the persisted plan.
                        ctx.goal.metadata["in_flight_batch"] = True
                        self._persistence.save_goal(ctx.goal)
                        batch_results = await execute_plan(ctx.goal, plan)
                        if not isinstance(batch_results, list) or len(batch_results) != total_steps:
                            ctx.goal.metadata["batch_partial_execution"] = True
                            ctx.goal.metadata["execution_state_untrusted"] = True
                            ctx.goal.metadata["verification_status"] = "not_verified"
                            raise GoalInterventionRequired(
                                f"Batch executor returned {len(batch_results) if isinstance(batch_results, list) else 'invalid'} "
                                f"results for {total_steps} planned steps."
                            )
                        for index, step_result in enumerate(batch_results):
                            if not isinstance(step_result, dict):
                                ctx.goal.metadata["batch_partial_execution"] = True
                                ctx.goal.metadata["execution_state_untrusted"] = True
                                ctx.goal.metadata["verification_status"] = "not_verified"
                                raise GoalInterventionRequired(
                                    f"Batch result {index + 1} is not structured; execution state requires review."
                                )
                            if step_result.get("verification_status") != "verified":
                                # The batch may already have changed external state. Never
                                # replan/replay a batch when its postcondition is unknown.
                                ctx.goal.metadata["batch_partial_execution"] = True
                                ctx.goal.metadata["execution_state_untrusted"] = True
                                ctx.goal.metadata["verification_status"] = "not_verified"
                                raise GoalInterventionRequired(
                                    f"Batch step {index + 1} has no independent verification; "
                                    "execution state requires operator review."
                                )
                            results = ctx.goal.metadata.setdefault("execution_results", [])
                            results.append(step_result)
                            if step_result.get("verification_status"):
                                ctx.goal.metadata["verification_status"] = step_result["verification_status"]
                            completed_steps += 1
                            self._persistence.save_goal(ctx.goal)
                            self._publish_event("goal.progress", {
                                "goal_id": goal_id.value,
                                "percentage": str((completed_steps / total_steps) * 100)
                            })
                        ctx.goal.metadata.pop("in_flight_batch", None)
                        ctx.goal.metadata.pop("in_flight_step_id", None)
                        ctx.goal.metadata.pop("execution_state_untrusted", None)
                        ctx.goal.metadata.pop("batch_partial_execution", None)
                        ctx.goal.metadata["verification_status"] = "verified"
                        self._persistence.save_goal(ctx.goal)
                    else:
                        for wave in waves:
                            if ctx.goal.state != GoalState.RUNNING:
                                break
                            for step in wave:
                                ctx.goal.metadata["in_flight_step_id"] = step.id.value
                                self._persistence.save_goal(ctx.goal)
                                step_result = await self._step_executor.execute(ctx.goal, step)
                                if (
                                    not isinstance(step_result, dict)
                                    or step_result.get("verification_status") != "verified"
                                ):
                                    # The tool may have acted even when it returned no
                                    # trustworthy postcondition. Pause for reconciliation;
                                    # do not treat this as a safe retry/replan opportunity.
                                    ctx.goal.metadata["execution_state_untrusted"] = True
                                    ctx.goal.metadata["verification_status"] = "not_verified"
                                    raise GoalInterventionRequired(
                                        f"Step {step.id.value} did not return independent verification; "
                                        "the outcome may be unknown and requires operator review."
                                    )
                                ctx.goal.metadata.pop("in_flight_step_id", None)
                                results = ctx.goal.metadata.setdefault("execution_results", [])
                                results.append(step_result)
                                ctx.goal.metadata["verification_status"] = "verified"
                                self._persistence.save_goal(ctx.goal)
                                completed_steps += 1
                            self._publish_event("goal.progress", {
                                "goal_id": goal_id.value,
                                "percentage": str((completed_steps / total_steps) * 100)
                            })
                    if ctx.goal.state == GoalState.RUNNING and completed_steps != total_steps:
                        raise GoalExecutionError(
                            f"Execution stopped after {completed_steps}/{total_steps} steps for goal {goal_id.value}."
                        )
                    break
                except Exception as step_exc:
                    replan = getattr(self._planner, "replan_after_failure", None)
                    if (
                        isinstance(step_exc, GoalInterventionRequired)
                        or ctx.goal.metadata.get("execution_state_untrusted", False)
                        or completed_steps != 0
                        or ctx.goal.metadata.get("batch_partial_execution", False)
                        # A failure before the first recorded result does not prove
                        # that the action had no side effects. Replanning is allowed
                        # only when the execution adapter independently attests that
                        # replay is safe.
                        or not ctx.goal.metadata.get("safe_replan_allowed", False)
                        or ctx.goal.metadata.get("replan_attempts", 0) >= 1
                        or not callable(replan)
                    ):
                        raise
                    # The executor has explicitly attested that this failure is safe
                    # to replay. Clear the in-flight marker only under that attestation.
                    ctx.goal.metadata.pop("in_flight_step_id", None)
                    ctx.goal.metadata.pop("in_flight_batch", None)
                    ctx.goal.metadata.pop("execution_state_untrusted", None)
                    ctx.goal.metadata["replan_attempts"] = 1
                    ctx.goal.metadata["replan_failure_reason"] = str(step_exc)[:1000]
                    self._persistence.save_goal(ctx.goal)
                    replacement = replan(ctx.goal, plan, str(step_exc))
                    if replacement is None or not replacement.steps:
                        raise
                    plan = replacement
                    self._persistence.save_plan(plan)
                    self._publish_event("goal.replanned", {
                        "goal_id": goal_id.value,
                        "attempt": "1",
                        "reason": "safe bounded recovery after a replay-safe plan failed",
                    })
                    continue

            if ctx.goal.state == GoalState.RUNNING:
                ctx.set_state(GoalState.COMPLETED)
                self._persistence.save_goal(ctx.goal)
                self._publish_event("goal.completed", {"goal_id": goal_id.value})
                
                # Run Evaluation
                eval_history = GoalHistory(goal_id=goal_id, logs=[])
                self._evaluator.evaluate(ctx.goal, eval_history)
                
        except asyncio.CancelledError:
            pass
        except GoalInterventionRequired as exc:
            ctx = self._active_contexts.get(goal_id.value)
            if ctx and ctx.goal.state == GoalState.RUNNING:
                # An explicit approval gate before any completed action is safe to
                # revisit. If prior/unknown work exists, retain the in-flight markers
                # and require the crash-safe ledger to reconcile it.
                if (
                    not ctx.goal.metadata.get("execution_state_untrusted")
                    and not ctx.goal.metadata.get("batch_partial_execution")
                    and not ctx.goal.metadata.get("execution_results")
                ):
                    ctx.goal.metadata.pop("in_flight_step_id", None)
                    ctx.goal.metadata.pop("in_flight_batch", None)
                else:
                    # This manager restarts generic plans from their first step.
                    # Previously completed steps therefore make replay unsafe even
                    # if the current intervention itself is an approval gate.
                    ctx.goal.metadata["execution_state_untrusted"] = True
                    ctx.goal.metadata["verification_status"] = "not_verified"
                reason_lower = str(exc).casefold()
                if "approval" in reason_lower or "confirmation" in reason_lower:
                    intervention_kind = "approval_required"
                elif "denied" in reason_lower or "policy" in reason_lower:
                    intervention_kind = "policy_denied"
                elif "unknown outcome" in reason_lower or "reconcile" in reason_lower or "needs_review" in reason_lower:
                    intervention_kind = "unknown_outcome"
                else:
                    intervention_kind = "manual_intervention"
                ctx.goal.metadata["intervention_kind"] = intervention_kind
                ctx.goal.metadata["intervention_required"] = str(exc)[:1000]
                plan = self._persistence.get_plan(goal_id)
                if plan and plan.steps:
                    mission_id = plan.steps[0].context.get("mission_id")
                    if isinstance(mission_id, str) and mission_id:
                        ctx.goal.metadata["mission_id"] = mission_id
                ctx.set_state(GoalState.PAUSED)
                self._persistence.save_goal(ctx.goal)
                self._logger.warning(
                    "Goal %s paused for operator intervention: %s",
                    goal_id.value,
                    exc,
                )
                self._publish_event("goal.intervention_required", {
                    "goal_id": goal_id.value,
                    "reason": str(exc)[:500],
                })
        except Exception as exc:  # noqa: BLE001 - persist failure for callers and recovery
            ctx = self._active_contexts.get(goal_id.value)
            if ctx:
                if (
                    ctx.goal.metadata.get("in_flight_step_id")
                    or ctx.goal.metadata.get("in_flight_batch")
                    or ctx.goal.metadata.get("execution_state_untrusted")
                    or ctx.goal.metadata.get("batch_partial_execution")
                ):
                    ctx.goal.metadata["execution_state_untrusted"] = True
                    ctx.goal.metadata["verification_status"] = "not_verified"
                    ctx.goal.metadata["intervention_kind"] = "unknown_outcome"
                    ctx.goal.metadata["intervention_required"] = (
                        f"Execution stopped with an unknown outcome ({type(exc).__name__}: {str(exc)[:500]}). "
                        "Reconcile the durable execution ledger before continuing."
                    )
                    ctx.set_state(GoalState.PAUSED)
                    self._persistence.save_goal(ctx.goal)
                    self._logger.warning("Goal %s paused for reconciliation: %s", goal_id.value, exc)
                    self._publish_event("goal.intervention_required", {
                        "goal_id": goal_id.value, "reason": str(exc)[:500],
                    })
                else:
                    ctx.goal.metadata["failure_reason"] = str(exc)
                    ctx.set_state(GoalState.FAILED)
                    self._persistence.save_goal(ctx.goal)
                    self._logger.error("Goal %s failed: %s", goal_id.value, exc)
                    self._publish_event("goal.failed", {"goal_id": goal_id.value, "reason": str(exc)})

    def _publish_event(self, topic: str, payload: dict[str, str]) -> None:
        event = Event(
            topic=topic,
            payload=payload,
            source=self.metadata.id
        )
        self._event_bus.publish(event)
