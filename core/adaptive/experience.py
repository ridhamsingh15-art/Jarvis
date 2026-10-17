from typing import Any

from core.models.primitives import Identifier, Metadata

from .interfaces import ExperienceCollector
from .models import Experience


class DefaultExperienceCollector(ExperienceCollector):
    """Generates experiences from execution outcomes."""

    def record_mission(
        self,
        user_input: str,
        success: bool,
        duration: float,
        **kwargs: Any
    ) -> Experience:
        intent = kwargs.get("intent")
        workflow_id = kwargs.get("workflow_id")
        skill_id = kwargs.get("skill_id")
        tasks = kwargs.get("tasks", [])
        
        # Build metadata safely
        meta_dict = kwargs.get("metadata", {})
        if not isinstance(meta_dict, dict):
            meta_dict = {}
        
        return Experience(
            user_input=user_input,
            success=success,
            duration=duration,
            intent=intent,
            workflow_id=Identifier(workflow_id) if workflow_id else None,
            skill_id=Identifier(skill_id) if skill_id else None,
            tasks=tasks,
            metadata=Metadata(annotations=meta_dict)
        )
