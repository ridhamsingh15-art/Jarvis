"""
The Runtime Kernel facade orchestrator.
"""
from collections.abc import Awaitable, Callable

from .health import HealthMonitor
from .interfaces import RuntimeComponent
from .lifecycle import LifecycleManager
from .models import HealthReport
from .registry import ComponentRegistry


class RuntimeManager:
    """
    Central facade managing component registration, lifecycle, and health.
    """

    def __init__(
        self,
        registry: ComponentRegistry | None = None,
        lifecycle: LifecycleManager | None = None,
        health_monitor: HealthMonitor | None = None,
    ) -> None:
        """
        Initializes the RuntimeManager with dependency injection support.
        """
        self.registry = registry or ComponentRegistry()
        self.lifecycle = lifecycle or LifecycleManager(self.registry)
        self.health_monitor = health_monitor or HealthMonitor(self.registry)

    def register(self, component: RuntimeComponent) -> None:
        """Registers a new component."""
        self.registry.register(component)

    async def start(self) -> None:
        """Starts all components in dependency order and begins health monitoring."""
        await self.lifecycle.start_all()
        await self.health_monitor.start()

    async def stop(self) -> None:
        """Stops health monitoring and all components safely."""
        await self.health_monitor.stop()
        await self.lifecycle.stop_all()

    def get_health_reports(self) -> list[HealthReport]:
        """Returns the latest health diagnostic reports across the OS."""
        return self.health_monitor.get_reports()

    def set_event_callback(self, callback: Callable[[HealthReport], Awaitable[None]]) -> None:
        """Allows injecting an EventBus bridge for health degradation alerts."""
        self.health_monitor.on_health_degraded = callback
