import logging
from typing import List, Optional
from .models import ProgressReport, WorkflowNode, ProductionState

logger = logging.getLogger(__name__)

class ProgressTracker:
    """Tracks overall mission progress for the Creator Agent."""

    def __init__(self, mission_id: str, workflow_sequence: List[WorkflowNode]):
        self.mission_id = mission_id
        self.total_nodes = len(workflow_sequence)
        self.workflow_sequence = workflow_sequence
        self.completed_nodes = 0
        
    def generate_report(self) -> ProgressReport:
        completed = []
        skipped = []
        failed = []
        running = None
        
        for node in self.workflow_sequence:
            if node.state == ProductionState.COMPLETED:
                completed.append(node.id)
            elif node.state == ProductionState.SKIPPED:
                skipped.append(node.id)
            elif node.state == ProductionState.FAILED:
                failed.append(node.id)
            elif node.state == ProductionState.RUNNING:
                running = node.id
                
        # Calculate percentage (completed + skipped) / total
        completed_count = len(completed) + len(skipped)
        pct = (completed_count / self.total_nodes) * 100 if self.total_nodes > 0 else 100.0
        
        return ProgressReport(
            mission_id=self.mission_id,
            overall_progress_percent=round(pct, 2),
            completed_stages=completed,
            running_stage=running,
            failed_stages=failed,
            skipped_stages=skipped
        )

    def log_progress(self) -> None:
        """Logs user-friendly progress strings based on current state."""
        report = self.generate_report()
        
        if report.running_stage:
            node = next((n for n in self.workflow_sequence if n.id == report.running_stage), None)
            if node:
                msg_map = {
                    "research": "Researching topic...",
                    "script": "Writing script...",
                    "storyboard": "Generating storyboard panels...",
                    "images": "Generating visual assets...",
                    "animation": "Rendering animation...",
                    "voice": "Generating voiceovers...",
                    "edit": "Assembling final video...",
                    "publish": "Publishing to YouTube...",
                    "analytics": "Tracking metrics..."
                }
                status_msg = msg_map.get(node.id, f"Executing {node.id}...")
                logger.info(f"[{report.overall_progress_percent}%] {status_msg}")
        elif report.failed_stages:
            logger.error(f"Production halted. Failed stages: {', '.join(report.failed_stages)}")
        elif report.overall_progress_percent == 100.0:
            logger.info("[100%] Production complete.")
