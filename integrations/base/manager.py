from typing import Any

from core.events.bus import EventBus
from core.models import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .interface import BaseIntegration


class IntegrationManager(RuntimeComponent):
    def __init__(self, event_bus: EventBus):
        self._id = Identifier("manager.integrations")
        self.event_bus = event_bus
        self.integrations: dict[str, BaseIntegration] = {}
        self._is_running = False

    def register(self, name: str, integration: BaseIntegration) -> None:
        self.integrations[name] = integration

    @property
    def id(self) -> Identifier:
        return self._id

    @property
    def metadata(self) -> ComponentMetadata:
        return ComponentMetadata(id=self._id.value, name="Integration Platform", version="1.0.0")

    @property
    def state(self) -> ComponentState:
        return ComponentState.RUNNING if self._is_running else ComponentState.STOPPED

    async def initialize(self) -> None:
        for name, integration in self.integrations.items():
            await integration.connect()
            await self.event_bus.publish_async(Event(
                topic="integration.connected",
                payload={"name": name}
            ))

    async def start(self) -> None:
        self._is_running = True

    async def stop(self) -> None:
        self._is_running = False
        for integration in self.integrations.values():
            await integration.disconnect()

    async def health(self) -> HealthReport:
        return HealthReport(
            component_id=self._id.value,
            state=HealthState.HEALTHY if self._is_running else HealthState.UNKNOWN
        )

    async def execute(self, integration_name: str, action: str, params: dict[str, Any]) -> Any:
        if integration_name not in self.integrations:
            raise ValueError(f"Integration {integration_name} not found")
            
        integration = self.integrations[integration_name]
        if action not in integration.capabilities():
            raise ValueError(f"Action {action} not supported by {integration_name}")
            
        try:
            result = await integration.execute(action, params)
            await self.event_bus.publish_async(Event(
                topic="integration.executed",
                payload={"name": integration_name, "action": action}
            ))
            return result
        except Exception as e:
            await self.event_bus.publish_async(Event(
                topic="integration.failed",
                payload={"name": integration_name, "action": action, "error": str(e)}
            ))
            raise
