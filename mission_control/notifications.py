from core.events.bus import EventBus
from core.models import Event


class NotificationCenter:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    async def notify(self, topic: str, mission_id: str, extra: dict | None = None) -> None:
        payload = {"mission_id": mission_id}
        if extra:
            payload.update(extra)
        await self.event_bus.publish_async(Event(topic=topic, payload=payload))
