"""
Capability Planner — translates LLM output into an immutable CapabilityPlan.
"""

from typing import Any

from core.capability.exceptions import RoutingError
from core.capability.models import CapabilityPlan


class CapabilityPlanner:
    """Parses and constructs a CapabilityPlan from LLM routing output."""

    def build_plan(self, raw_output: dict[str, Any]) -> CapabilityPlan:
        """Construct the immutable plan from raw dictionary output.
        
        Args:
            raw_output: JSON parsed output from the router model.
            
        Returns:
            The structured CapabilityPlan.
            
        Raises:
            RoutingError: If the output is missing critical fields or malformed.
        """
        try:
            return CapabilityPlan(
                reasoning_model=raw_output.get("reasoning_model", "auto"),
                required_capabilities=raw_output.get("required_capabilities", []),
                required_tools=raw_output.get("required_tools", []),
                requires_planner=bool(raw_output.get("requires_planner", False)),
                requires_memory=bool(raw_output.get("requires_memory", False)),
                requires_workspace=bool(raw_output.get("requires_workspace", False)),
                requires_knowledge=bool(raw_output.get("requires_knowledge", False)),
                requires_internet=bool(raw_output.get("requires_internet", False)),
                requires_automation=bool(raw_output.get("requires_automation", False)),
                requires_scripting=bool(raw_output.get("requires_scripting", False)),
                requires_storyboard=bool(raw_output.get("requires_storyboard", False)),
                requires_project_management=bool(raw_output.get("requires_project_management", False)),
                requires_image_generation=bool(raw_output.get("requires_image_generation", False)),
                requires_animation=bool(raw_output.get("requires_animation", False)),
                requires_voice=bool(raw_output.get("requires_voice", False)),
                requires_video=bool(raw_output.get("requires_video", False)),
                requires_music=bool(raw_output.get("requires_music", False)),
                requires_subtitles=bool(raw_output.get("requires_subtitles", False)),
                requires_thumbnail=bool(raw_output.get("requires_thumbnail", False)),
                requires_seo=bool(raw_output.get("requires_seo", False)),
                requires_publishing=bool(raw_output.get("requires_publishing", False)),
                requires_analytics=bool(raw_output.get("requires_analytics", False)),
                requires_agents=bool(raw_output.get("requires_agents", False)),
                requires_execution=bool(raw_output.get("requires_execution", False)),
                estimated_complexity=raw_output.get("estimated_complexity", "low"),
                estimated_cost=raw_output.get("estimated_cost", "low"),
                estimated_latency=raw_output.get("estimated_latency", "low"),
                confidence=float(raw_output.get("confidence", 1.0)),
                style=str(raw_output.get("style", "storytelling")),
            )
        except (ValueError, TypeError) as exc:
            raise RoutingError(f"Failed to parse capability plan: {exc}")
