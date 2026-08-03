from core.events.bus import EventBus
from core.models import Event


class InterruptHandler:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    async def interrupt(self, reason: str) -> None:
        await self.event_bus.publish_async(Event(
            topic="executive.interrupt",
            payload={"reason": reason, "action": "PAUSE_ALL"}
        ))
