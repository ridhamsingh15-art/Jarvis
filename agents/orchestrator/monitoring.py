from core.events.bus import EventBus
from core.models import Event

from .state import NodeState, WorkflowState


class WorkflowMonitor:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    async def log_status(self, state: WorkflowState) -> None:
        completed = sum(1 for v in state.node_states.values() if v == NodeState.COMPLETED)
        failed = sum(1 for v in state.node_states.values() if v == NodeState.FAILED)
        await self.event_bus.publish_async(Event(
            topic="orchestrator.status.update",
            payload={"workflow": state.id, "completed": completed, "failed": failed}
        ))
