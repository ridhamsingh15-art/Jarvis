
from core.events import EventBus
from core.runtime import BaseComponent, ComponentMetadata, HealthReport, RuntimeState
from core.tasks import Task, TaskManager
from core.workflows import Workflow, WorkflowManager

from .models import JobType
from .scheduler import SchedulerEngine
from .triggers import Trigger


class SchedulerManager(BaseComponent):
    """
    Central orchestration facade for scheduling workloads.
    Implements RuntimeComponent.
    """
    def __init__(self, event_bus: EventBus, task_manager: TaskManager, workflow_manager: WorkflowManager):
        super().__init__(ComponentMetadata(id="SchedulerEngine", name="Scheduler", version="1.0.0"))
        self._engine = SchedulerEngine(event_bus, task_manager, workflow_manager)
        self._event_bus = event_bus
        self._task_manager = task_manager
        
        # In a real system, we would subscribe to the EventBus natively via Runtime.
        # Here we bind a direct callback for testing intercepting 'task.failed'.
        self._event_bus.subscribe("task.failed", self._handle_task_failure)

    def schedule_task(self, task: Task, trigger: Trigger) -> str:
        """Schedules a Task for future execution."""
        return self._engine.schedule(task, trigger, JobType.TASK)

    def schedule_workflow(self, workflow: Workflow, trigger: Trigger) -> str:
        """Schedules a Workflow for future execution."""
        return self._engine.schedule(workflow, trigger, JobType.WORKFLOW)

    def cancel_schedule(self, schedule_id: str) -> bool:
        return self._engine.cancel(schedule_id)
        
    def _handle_task_failure(self, event):
        """Intercepts failure events to evaluate backoff policies and auto-retry."""
        task_dict = event.payload
        if not task_dict:
            return
            
        # TaskManager emits {"task_id": "string"}
        task_id = task_dict.get("task_id")
        if not task_id:
            return
            
        try:
            task = self._task_manager.get(task_id)
        except Exception:  # noqa: BLE001
            return
            
        # Check retry limits using the Task as the single source of truth
        if task.max_retries > 0 and task.retry_count < task.max_retries:
            from .policies import ExponentialBackoff
            from .triggers import DelayedTrigger
            
            attempt = task.retry_count + 1
            
            # Compute real backoff delay using the actual attempt
            policy = ExponentialBackoff(base_delay=1.0)
            delay = policy.next_delay(attempt)
            
            trigger = DelayedTrigger(delay)
            self._engine.schedule(task, trigger, JobType.TASK)

    # RuntimeComponent overrides
    async def _do_start(self) -> None:
        self._engine.start()

    async def _do_stop(self) -> None:
        self._engine.stop()

    async def health(self) -> HealthReport:
        is_healthy = self.state == RuntimeState.RUNNING
        from core.runtime.enums import HealthState
        return HealthReport(
            component_id=self.metadata.id,
            state=HealthState.HEALTHY if is_healthy else HealthState.DEGRADED,
            details={
                "queued_jobs": self._engine._queue.qsize()
            }
        )
