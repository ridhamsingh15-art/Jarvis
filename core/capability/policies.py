"""
Policies for the Capability Router.
"""

from core.capability.models import CapabilityPlan


class RoutingPolicy:
    """Enforces Executive-level rules on routing decisions."""

    def __init__(self, offline_mode: bool = False) -> None:
        self.offline_mode = offline_mode

    def enforce(self, plan: CapabilityPlan) -> CapabilityPlan:
        """Apply policies to a generated plan.
        
        Args:
            plan: The proposed capability plan.
            
        Returns:
            The potentially modified (enforced) plan.
        """
        # We need to create a new object or modify dict before construction,
        # but since CapabilityPlan is a frozen dataclass, we must use object.__setattr__
        # or replace. To keep it simple, we construct a new one.
        
        new_internet = plan.requires_internet
        new_tools = list(plan.required_tools)
        new_caps = list(plan.required_capabilities)
        
        if self.offline_mode:
            new_internet = False
            if "browser" in new_tools:
                new_tools.remove("browser")
            if "Internet" in new_caps:
                new_caps.remove("Internet")
                
        return CapabilityPlan(
            reasoning_model=plan.reasoning_model,
            required_capabilities=new_caps,
            required_tools=new_tools,
            requires_planner=plan.requires_planner,
            requires_memory=plan.requires_memory,
            requires_workspace=plan.requires_workspace,
            requires_knowledge=plan.requires_knowledge,
            requires_internet=new_internet,
            requires_agents=plan.requires_agents,
            requires_execution=plan.requires_execution,
            estimated_complexity=plan.estimated_complexity,
            estimated_cost=plan.estimated_cost,
            estimated_latency=plan.estimated_latency,
            confidence=plan.confidence
        )
