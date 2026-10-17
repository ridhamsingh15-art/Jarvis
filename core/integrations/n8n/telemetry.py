"""
Telemetry integration for n8n workflows.
"""

from typing import Any

from core.events.bus import EventBus
from core.models import Event


class N8nTelemetry:
    """Publishes execution telemetry to the global EventBus."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def emit_workflow_started(self, workflow_name: str, execution_id: str) -> None:
        self._event_bus.publish(Event(
            topic="N8nWorkflowStarted",
            payload={"workflow": workflow_name, "execution_id": execution_id},
            source="n8n.telemetry"
        ))

    def emit_workflow_finished(self, workflow_name: str, execution_id: str, duration: float) -> None:
        self._event_bus.publish(Event(
            topic="N8nWorkflowFinished",
            payload={"workflow": workflow_name, "execution_id": execution_id, "duration": duration},
            source="n8n.telemetry"
        ))

    def emit_workflow_failed(self, workflow_name: str, execution_id: str, error: str) -> None:
        self._event_bus.publish(Event(
            topic="N8nWorkflowFailed",
            payload={"workflow": workflow_name, "execution_id": execution_id, "error": error},
            source="n8n.telemetry"
        ))

    def emit_workflow_output(self, workflow_name: str, execution_id: str, data: dict[str, Any]) -> None:
        self._event_bus.publish(Event(
            topic="N8nWorkflowOutput",
            payload={"workflow": workflow_name, "execution_id": execution_id, "data": data},
            source="n8n.telemetry"
        ))
