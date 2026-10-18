from collections.abc import Callable

from core.events import EventBus
from core.models import Event, ExecutionResult
from core.runtime import BaseComponent, ComponentMetadata, HealthReport, RuntimeState
from core.tasks import TaskManager

from .action_registry import ActionRegistry
from .dispatcher import TaskDispatcher
from .executor import ExecutionEngine
from .isolated_handler import IsolatedToolHandler
from .models import ExecutionContext
from .pool import WorkerPool
from .timeouts import TimeoutEnforcer
from .worker import WorkerThread


class ExecutorManager(BaseComponent):
    """
    Central orchestration facade for executing workloads.
    Implements RuntimeComponent.
    """
    def __init__(self, event_bus: EventBus, task_manager: TaskManager, min_workers: int = 2, max_workers: int = 10):
        super().__init__(ComponentMetadata(id="ExecutorEngine", name="Executor", version="1.0.0"))
        self._event_bus = event_bus
        self._task_manager = task_manager
        
        self.registry = ActionRegistry()
        self._engine = ExecutionEngine(self.registry)
        
        self._timeouts = TimeoutEnforcer()
        self._pool = WorkerPool("JarvisExecutor", min_workers, max_workers, self._engine.execute_context, self._handle_worker_completion)
        self._dispatcher = TaskDispatcher(task_manager, self._pool, self._timeouts, self._engine)
        # Compatibility registrations remain available, but are explicitly reported
        # as legacy/uncontained until callers classify them via register_action.
        self._action_contracts: dict[str, str] = {}
        self._registered_handlers: dict[str, Callable] = {}

    def register_action(
        self,
        action_name: str,
        handler: Callable,
        *,
        side_effecting: bool = False,
    ) -> None:
        """Register an action with an explicit containment contract.

        Existing two-argument callers retain their historical behavior. New
        side-effecting actions must pass ``side_effecting=True`` and supply an
        ``IsolatedToolHandler``; raw callbacks are rejected for that contract.
        Legacy registrations are tracked as ``legacy-uncontained`` so release
        checks can fail closed instead of mistaking compatibility for safety.
        A handler's return value is execution output, not independent verification.
        """
        if not isinstance(action_name, str) or not action_name.strip():
            raise ValueError("action_name must be a non-empty string")
        if not callable(handler):
            raise TypeError("handler must be callable")
        if not isinstance(side_effecting, bool):
            raise TypeError("side_effecting must be a bool")
        if side_effecting and not isinstance(handler, IsolatedToolHandler):
            raise TypeError(
                "Side-effecting actions require IsolatedToolHandler containment; "
                "raw callbacks are not accepted for this contract."
            )
        if side_effecting:
            handler.validate_configuration()
        self.registry.register(action_name, handler)
        self._action_contracts[action_name] = (
            "isolated-side-effect" if side_effecting else "legacy-uncontained"
        )
        self._registered_handlers[action_name] = handler

    def registration_audit(self) -> dict[str, object]:
        """Return a snapshot that detects legacy registrations and registry bypasses."""
        contracts = dict(self._action_contracts)
        registered_actions = self.registry.list_actions()
        uncontained = []
        for name in registered_actions:
            current_handler = self.registry.get(name)
            declared_handler = self._registered_handlers.get(name)
            contract = contracts.get(name)
            if declared_handler is not current_handler:
                contracts[name] = "unclassified-or-replaced-direct-registry-entry"
                uncontained.append(name)
            elif contract != "isolated-side-effect":
                uncontained.append(name)
        return {
            "registered_actions": registered_actions,
            "contracts": contracts,
            "uncontained_actions": sorted(uncontained),
            "release_safe": not uncontained,
        }

    def _handle_worker_completion(self, worker: WorkerThread, context: ExecutionContext, result: ExecutionResult):
        """Callback invoked by a WorkerThread when it finishes an assignment."""
        self._timeouts.untrack(context.task.task_id.value)
        
        if result.success:
            final_task = self._task_manager.complete(context.task.task_id.value)
        else:
            final_task = self._task_manager.fail(context.task.task_id.value)
        
        # Emit Executor-specific events
        event_topic = "task.execution.finished" if result.success else "task.execution.failed"
        self._event_bus.publish(Event(topic=event_topic, payload=final_task.to_dict(), source="executor"))

    # RuntimeComponent overrides
    async def _do_start(self) -> None:
        self._timeouts.start()
        self._dispatcher.start()

    async def _do_stop(self) -> None:
        self._dispatcher.stop()
        self._pool.shutdown()
        self._timeouts.stop()

    async def health(self) -> HealthReport:
        is_healthy = self.state == RuntimeState.RUNNING
        stats = self._pool.get_stats()
        from core.runtime.enums import HealthState
        return HealthReport(
            component_id=self.metadata.id,
            state=HealthState.HEALTHY if is_healthy else HealthState.DEGRADED,
            details=stats
        )
