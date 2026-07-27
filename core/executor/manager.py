from typing import Dict, Any, Callable

from core.events import EventBus
from core.models import Event, ExecutionResult
from core.runtime import BaseComponent, HealthReport, RuntimeState
from core.tasks import TaskManager, TaskStatus

from .action_registry import ActionRegistry
from .executor import ExecutionEngine
from .pool import WorkerPool
from .timeouts import TimeoutEnforcer
from .dispatcher import TaskDispatcher
from .models import ExecutionContext
from .worker import WorkerThread

class ExecutorManager(BaseComponent):
    """
    Central orchestration facade for executing workloads.
    Implements RuntimeComponent.
    """
    def __init__(self, event_bus: EventBus, task_manager: TaskManager, min_workers: int = 2, max_workers: int = 10):
        super().__init__("ExecutorEngine")
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
        self._timeouts.untrack(context.task.id.value)
        
        # We must transition the task in the TaskManager
        final_status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
        
        # Re-attach the result to the task via transition kwargs
        final_task = self._task_manager.transition_task(
            context.task.id.value, 
            final_status,
            result=result
        )
        
        # Emit Executor-specific events
        event_topic = "task.execution.finished" if result.success else "task.execution.failed"
        self._event_bus.publish(Event(topic=event_topic, payload=final_task.to_dict(), source="executor"))

    # RuntimeComponent overrides
    def start(self) -> None:
        super().start()
        self._timeouts.start()
        self._dispatcher.start()

    def stop(self) -> None:
        super().stop()
        self._dispatcher.stop()
        self._pool.shutdown()
        self._timeouts.stop()

    def health(self) -> HealthReport:
        is_healthy = self._state == RuntimeState.RUNNING
        stats = self._pool.get_stats()
        return HealthReport(
            is_healthy=is_healthy,
            status=self._state.value,
            component_name=self._name,
            details=stats
        )
