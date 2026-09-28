from typing import List
from .models import WorkflowNode, ProductionState

class RecoveryManager:
    """Handles failure recovery and workflow resumption."""

    def resume_from_checkpoint(self, workflow_sequence: List[WorkflowNode], completed_stage_ids: List[str]) -> List[WorkflowNode]:
        """
        Takes a workflow sequence and marks previously completed stages as SKIPPED
        so they are not re-executed, while preserving the project bundle.
        """
        for node in workflow_sequence:
            if node.id in completed_stage_ids:
                node.state = ProductionState.SKIPPED
                
        return workflow_sequence

    def filter_runnable_sequence(self, workflow_sequence: List[WorkflowNode]) -> List[WorkflowNode]:
        """
        Returns only the nodes that actually need to be executed.
        """
        return [n for n in workflow_sequence if n.state == ProductionState.PENDING]
