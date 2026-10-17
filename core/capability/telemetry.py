"""
Telemetry for Capability Routing.
"""


from core.capability.models import CapabilityPlan
from core.events.bus import EventBus
from core.models.domain import Event


class CapabilityTelemetry:
    """Records routing decisions for observability."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def publish_routing_decision(
        self,
        user_input: str,
        plan: CapabilityPlan,
        selected_model: str,
        latency_ms: float
    ) -> None:
        """Publish the generated routing plan.
        
        Args:
            user_input: The original request.
            plan: The generated capability plan.
            selected_model: The name of the model selected to execute the plan.
            latency_ms: Time taken to generate the plan.
        """
        payload = {
            "request": user_input,
            "decision": {
                "requires_execution": plan.requires_execution,
                "requires_planner": plan.requires_planner,
                "requires_memory": plan.requires_memory,
                "requires_workspace": plan.requires_workspace,
                "requires_knowledge": plan.requires_knowledge,
                "requires_internet": plan.requires_internet,
                "requires_agents": plan.requires_agents,
                "capabilities": plan.required_capabilities,
                "tools": plan.required_tools,
            },
            "metrics": {
                "complexity": plan.estimated_complexity,
                "confidence": plan.confidence,
                "routing_latency_ms": latency_ms
            },
            "execution": {
                "selected_model": selected_model
            }
        }
        
        event = Event(topic="capability.routing", payload=payload)
        self._event_bus.publish(event)
