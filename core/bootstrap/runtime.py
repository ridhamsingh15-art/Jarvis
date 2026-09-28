from core.di import Container
from core.events import EventBus
from core.telemetry import AsyncLogger

from .lifecycle import LifecycleManager


class Runtime:
    """
    The canonical running state of JARVIS AIOS.
    Holds the finalized Foundation components.
    """
    def __init__(
        self, 
        container: Container, 
        event_bus: EventBus, 
        logger: AsyncLogger,
        lifecycle: LifecycleManager
    ):
        self._container = container
        self._event_bus = event_bus
        self._logger = logger
        self._lifecycle = lifecycle

    @property
    def container(self) -> Container:
        return self._container
        
    @property
    def event_bus(self) -> EventBus:
        return self._event_bus
        
    @property
    def logger(self) -> AsyncLogger:
        return self._logger
        
    @property
    def lifecycle(self) -> LifecycleManager:
        return self._lifecycle

    def shutdown(self) -> None:
        """Convenience method to trigger the lifecycle shutdown."""
        self._lifecycle.shutdown()
