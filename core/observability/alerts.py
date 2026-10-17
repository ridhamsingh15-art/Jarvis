from core.events.bus import EventBus
from core.models import Event

from .metrics import MetricsRegistry


class AlertEngine:
    def __init__(self, event_bus: EventBus, registry: MetricsRegistry):
        self.event_bus = event_bus
        self.registry = registry

    async def evaluate(self) -> None:
        ram = self.registry.get_gauge("system.ram.usage").value
        if ram > 90.0:
            await self.event_bus.publish_async(Event(
                topic="observability.alert.ram_high",
                payload={"usage": ram}
            ))
