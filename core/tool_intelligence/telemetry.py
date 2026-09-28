"""
Telemetry integration for the Tool Intelligence subsystem.
"""

from typing import Any

from core.events.bus import EventBus
from core.models.domain import Event
from core.tool_intelligence.models import IntelligenceOutcome


class IntelligenceTelemetry:
    """Publishes repair and validation metrics to the EventBus."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def publish_outcome(self, outcome: IntelligenceOutcome, original_tool: str, original_action: str, original_args: dict[str, Any]) -> None:
        """Publish the outcome of an intelligence pass.

        Args:
            outcome: The resulting outcome containing repaired task and metrics.
            original_tool: Raw tool name.
            original_action: Raw action name.
            original_args: Raw arguments.
        """
        payload = {
            "original_tool": original_tool,
            "original_action": original_action,
            "original_args": original_args,
            "repaired_tool": outcome.task.tool,
            "repaired_action": outcome.task.action,
            "repaired_args": outcome.task.args,
            "is_valid": outcome.is_valid,
            "was_repaired": outcome.metrics.was_repaired,
            "metrics": {
                "tool_name_repaired": outcome.metrics.tool_name_repaired,
                "action_name_repaired": outcome.metrics.action_name_repaired,
                "arguments_repaired": outcome.metrics.arguments_repaired,
            }
        }
        
        if outcome.error_message:
            payload["error"] = outcome.error_message

        # We publish to a specialized topic for the Future Capability Router
        event = Event(topic="intelligence.repair", payload=payload)
        self._event_bus.publish(event)
