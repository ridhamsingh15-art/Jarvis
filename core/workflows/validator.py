from typing import Set

from .enums import WorkflowStatus
from .exceptions import InvalidWorkflowTransitionError, WorkflowValidationError, CyclicDependencyError
from .graph import DependencyGraph

class WorkflowValidator:
    """Validates workflow definitions and state transitions."""
    
    VALID_TRANSITIONS = {
        WorkflowStatus.CREATED: {WorkflowStatus.READY},
        WorkflowStatus.READY: {WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED},
        WorkflowStatus.RUNNING: {WorkflowStatus.PAUSED, WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED},
        WorkflowStatus.PAUSED: {WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED},
        WorkflowStatus.COMPLETED: set(),
        WorkflowStatus.FAILED: set(),
        WorkflowStatus.CANCELLED: set()
    }
    
    @classmethod
    def validate_transition(cls, current_status: WorkflowStatus, new_status: WorkflowStatus) -> None:
        """Validates if a state transition is legal."""
        if new_status not in cls.VALID_TRANSITIONS[current_status]:
            raise InvalidWorkflowTransitionError(
                f"Cannot transition Workflow from {current_status.value} to {new_status.value}"
            )
            
    @classmethod
    def validate_graph(cls, graph: DependencyGraph, task_ids: Set[str]) -> None:
        """
        Validates the dependency graph.
        - Checks for cycles
        - Checks for missing dependencies (tasks in graph that aren't in task_ids)
        """
        if graph.detect_cycles():
            raise CyclicDependencyError("Cyclic dependency detected in workflow graph.")
            
        with graph._lock:
            # We are reaching into graph internals slightly here for validation speed, 
            # though it would be cleaner if graph exposed a .get_all_nodes()
            missing = graph._nodes - task_ids
            if missing:
                raise WorkflowValidationError(f"Missing task definitions for dependencies: {missing}")
