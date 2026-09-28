from collections.abc import Callable

from core.events import EventBus
from core.models import Event, ExecutionResult
from core.runtime import BaseComponent, ComponentMetadata, HealthReport, RuntimeState
from core.tasks import TaskManager

from .action_registry import ActionRegistry
from .dispatcher import TaskDispatcher
from .executor import ExecutionEngine
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
        self._dispatcher = TaskDispatcher(task_manager, self._pool, self._timeouts)

    def register_action(self, action_name: str, handler: Callable) -> None:
        """Registers a callable into the execution engine."""
        self.registry.register(action_name, handler)

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
