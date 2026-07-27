from typing import Dict, Any

from core.events import EventBus
from core.runtime import BaseComponent, HealthReport, RuntimeState
from core.tasks import TaskManager, TaskDefinition, TaskStatus
from core.workflows import WorkflowManager, WorkflowDefinition

from .scheduler import SchedulerEngine
from .models import JobType
from .triggers import Trigger
from .policies import BackoffPolicy

class SchedulerManager(BaseComponent):
    """
    Central orchestration facade for scheduling workloads.
    Implements RuntimeComponent.
    """
    def __init__(self, event_bus: EventBus, task_manager: TaskManager, workflow_manager: WorkflowManager):
        super().__init__("SchedulerEngine")
        self._engine = SchedulerEngine(event_bus, task_manager, workflow_manager)
        self._event_bus = event_bus
        self._task_manager = task_manager
        
        # In a real system, we would subscribe to the EventBus natively via Runtime.
        # Here we bind a direct callback for testing intercepting 'task.failed'.
        self._event_bus.subscribe("task.failed", self._handle_task_failure)

    def schedule_task(self, task: TaskDefinition, trigger: Trigger) -> str:
        """Schedules a Task for future execution."""
        return self._engine.schedule(task, trigger, JobType.TASK)

    def schedule_workflow(self, workflow: WorkflowDefinition, trigger: Trigger) -> str:
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
        except Exception:
            return
            
        # Check retry limits using the Task as the single source of truth
        if task.max_retries > 0 and task.retry_count < task.max_retries:
            from .triggers import DelayedTrigger
            from .policies import ExponentialBackoff
            
            attempt = task.retry_count + 1
            
            # Compute real backoff delay using the actual attempt
            policy = ExponentialBackoff(base_delay=1.0)
            delay = policy.next_delay(attempt)
            
            trigger = DelayedTrigger(delay)
            self._engine.schedule(task, trigger, JobType.TASK)

    # RuntimeComponent overrides
    def start(self) -> None:
        super().start()
        self._engine.start()

    def stop(self) -> None:
        super().stop()
        self._engine.stop()

    def health(self) -> HealthReport:
        is_healthy = self._state == RuntimeState.RUNNING
        return HealthReport(
            is_healthy=is_healthy,
            status=self._state.value,
            component_name=self._name,
            details={
                "queued_jobs": self._engine._queue.qsize()
            }
        )
