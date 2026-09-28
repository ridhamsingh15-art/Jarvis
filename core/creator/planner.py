from typing import List
from core.reasoning.execution_plan import ExecutionPlan
from .models import WorkflowNode

class CreatorPlanner:
    """Translates a Workflow sequence into an ExecutionPlan for the MasterCoordinator."""

    def create_execution_plan(self, workflow_sequence: List[WorkflowNode]) -> ExecutionPlan:
        """
        Takes the ordered sequence of WorkflowNodes and constructs a standard
        ExecutionPlan that the ExecutiveBrain / MasterCoordinator understands.
        """
        ordered_steps = []
        for node in workflow_sequence:
            # We map the capability directly into the intent string for the coordinator
            # e.g., "script_writing" -> "Generate script_writing"
            # Actually, MasterCoordinator's extract_capability parses the intent string.
            # So we can just use the capability itself or a structured intent.
            
            # MasterCoordinator understands these keywords: 
            # plan, code, write/script, storyboard, image/visual, anim, voice/audio, edit/assembl, publish, search/research, review, test
            
            intent_mapping = {
                "web_search": "Research topics",
                "script_writing": "Write the script",
                "storyboarding": "Generate storyboard",
                "image_generation": "Generate visual images",
                "animation": "Animate visuals",
                "voice_generation": "Generate voice audio",
                "video_assembly": "Assemble video edit",
                "publishing": "Publish content",
                "analytics": "Track analytics",
                "programming": "Write code",
                "quality_assurance": "Review content"
            }
            
            intent = intent_mapping.get(node.capability, f"Execute {node.capability}")
            ordered_steps.append(intent)
            
        plan = ExecutionPlan(
            ordered_steps=ordered_steps,
            requires_project=True, # The Creator agent requires a shared project bundle
            fallback_strategy="Halt and request user intervention"
        )
        return plan
