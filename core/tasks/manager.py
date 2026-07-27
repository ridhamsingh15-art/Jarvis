from typing import List, Optional
from dataclasses import replace

from core.events import EventBus
from core.models import Event, Timestamp
from .enums import TaskStatus
from .models import Task
from .interfaces import TaskRepository
from .validators import TaskValidator
from .queue import TaskQueue

class TaskManager:
    """Orchestrates Task lifecycles, validation, queueing, and tracking."""
    
    def __init__(self, repository: TaskRepository, event_bus: EventBus):
        self._repository = repository
        self._event_bus = event_bus
        self._queue = TaskQueue()
        
    def _transition_status(self, task: Task, new_status: TaskStatus) -> Task:
        """Validates and applies a status transition, publishing the event."""
        TaskValidator.validate_transition(task.status, new_status)
            
        now = Timestamp()
        kwargs = {
            "status": new_status,
            "updated_at": now
        }
        
        if new_status == TaskStatus.RUNNING and task.started_at is None:
            kwargs["started_at"] = now
        elif new_status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            kwargs["completed_at"] = now
            
        updated = replace(task, **kwargs)
        self._repository.save(updated)
        
        event_action = new_status.value.capitalize()
        topic = f"Task{event_action}"
        
        self._event_bus.publish(Event(topic=topic, payload={"task_id": updated.task_id.value}))
        return updated

    def create(self, task: Task) -> Task:
        """Saves a new task and triggers TaskCreated."""
        TaskValidator.validate_task_configuration(task.timeout_seconds, task.retry_count, task.max_retries)
        self._repository.save(task)
        self._event_bus.publish(Event(topic="TaskCreated", payload={"task_id": task.task_id.value}))
        return task
        
    def get(self, task_id: str) -> Task:
        return self._repository.get(task_id)
        
    def list(self) -> List[Task]:
        return self._repository.list()
        
    def update(self, task_id: str, progress: Optional[float] = None, **kwargs) -> Task:
        """Updates specific safe fields like progress."""
        task = self.get(task_id)
        
        updates = {"updated_at": Timestamp()}
        if progress is not None:
            if not (0.0 <= progress <= 100.0):
                raise ValueError("Progress must be between 0 and 100")
            updates["progress"] = progress
            
        updated = replace(task, **updates)
        return self._repository.save(updated)
        
    def delete(self, task_id: str) -> None:
        self._repository.delete(task_id)
        
    # State transition wrappers
    def ready(self, task_id: str) -> Task:
        return self._transition_status(self.get(task_id), TaskStatus.READY)
        
    def queue(self, task_id: str) -> Task:
        """Transitions task to QUEUED and pushes onto the FIFO queue."""
        task = self._transition_status(self.get(task_id), TaskStatus.QUEUED)
        self._queue.enqueue(task)
        return task
        
    def block(self, task_id: str) -> Task:
        return self._transition_status(self.get(task_id), TaskStatus.BLOCKED)
        
    def resume(self, task_id: str) -> Task:
        # Used for QUEUED -> RUNNING and PAUSED -> RUNNING
        return self._transition_status(self.get(task_id), TaskStatus.RUNNING)
        
    def pause(self, task_id: str) -> Task:
        return self._transition_status(self.get(task_id), TaskStatus.PAUSED)
        
    def cancel(self, task_id: str) -> Task:
        return self._transition_status(self.get(task_id), TaskStatus.CANCELLED)
        
    def complete(self, task_id: str) -> Task:
        return self._transition_status(self.get(task_id), TaskStatus.COMPLETED)
        
    def fail(self, task_id: str) -> Task:
        return self._transition_status(self.get(task_id), TaskStatus.FAILED)
