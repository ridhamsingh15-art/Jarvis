from dataclasses import replace
from typing import Any

from core.events import EventBus
from core.models import Event, Timestamp

from .enums import WorkflowStatus
from .graph import DependencyGraph
from .interfaces import WorkflowRepository
from .models import Workflow
from .validator import WorkflowValidator


class WorkflowManager:
    """Orchestrates Workflow lifecycles, validation, and graph mappings."""
    
    def __init__(self, repository: WorkflowRepository, event_bus: EventBus):
        self._repository = repository
        self._event_bus = event_bus
        # Map of workflow_id -> DependencyGraph
        self._graphs: dict[str, DependencyGraph] = {}
        
    def _transition_status(self, workflow: Workflow, new_status: WorkflowStatus) -> Workflow:
        """Validates and applies a status transition, publishing the event."""
        WorkflowValidator.validate_transition(workflow.status, new_status)
            
        now = Timestamp()
        kwargs: dict[str, Any] = {
            "status": new_status,
            "updated_at": now
        }
        
        if new_status == WorkflowStatus.RUNNING and workflow.started_at is None:
            kwargs["started_at"] = now
        elif new_status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED):
            kwargs["completed_at"] = now
            
        updated = replace(workflow, **kwargs)
        self._repository.save(updated)
        
        event_action = new_status.value.capitalize()
        topic = f"Workflow{event_action}"
        
        self._event_bus.publish(Event(topic=topic, payload={"workflow_id": updated.workflow_id.value}))
        return updated

    def create(self, workflow: Workflow) -> Workflow:
        """Saves a new workflow and triggers WorkflowCreated."""
        self._repository.save(workflow)
        self._graphs[workflow.workflow_id.value] = DependencyGraph()
        self._event_bus.publish(Event(topic="WorkflowCreated", payload={"workflow_id": workflow.workflow_id.value}))
        return workflow
        
    def get(self, workflow_id: str) -> Workflow:
        return self._repository.get(workflow_id)
        
    def list(self) -> list[Workflow]:
        return self._repository.list()
        
    def update(self, workflow_id: str, progress: float | None = None, **kwargs) -> Workflow:
        """Updates specific safe fields like progress."""
        workflow = self.get(workflow_id)
        
        updates: dict[str, Any] = {"updated_at": Timestamp()}
        if progress is not None:
            if not (0.0 <= progress <= 100.0):
                raise ValueError("Progress must be between 0 and 100")
            updates["progress"] = progress
            
        updated = replace(workflow, **updates)
        return self._repository.save(updated)
        
    # State transition wrappers
    def ready(self, workflow_id: str) -> Workflow:
        return self._transition_status(self.get(workflow_id), WorkflowStatus.READY)
        
    def resume(self, workflow_id: str) -> Workflow:
        # Used for both READY -> RUNNING and PAUSED -> RUNNING
        return self._transition_status(self.get(workflow_id), WorkflowStatus.RUNNING)
        
    def pause(self, workflow_id: str) -> Workflow:
        return self._transition_status(self.get(workflow_id), WorkflowStatus.PAUSED)
        
    def cancel(self, workflow_id: str) -> Workflow:
        return self._transition_status(self.get(workflow_id), WorkflowStatus.CANCELLED)
        
    def complete(self, workflow_id: str) -> Workflow:
        return self._transition_status(self.get(workflow_id), WorkflowStatus.COMPLETED)
        
    def fail(self, workflow_id: str) -> Workflow:
        return self._transition_status(self.get(workflow_id), WorkflowStatus.FAILED)
        
    def delete(self, workflow_id: str) -> None:
        self._repository.delete(workflow_id)
        if workflow_id in self._graphs:
            del self._graphs[workflow_id]
            
    # Graph Management
    def get_graph(self, workflow_id: str) -> DependencyGraph:
        self.get(workflow_id) # ensure it exists
        if workflow_id not in self._graphs:
            self._graphs[workflow_id] = DependencyGraph()
        return self._graphs[workflow_id]
