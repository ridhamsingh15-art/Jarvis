import threading

from core.di import Container
from core.events import EventBus
from core.models import Event
from core.telemetry import AsyncLogger


class LifecycleManager:
    """Manages the state transitions and graceful shutdown of the runtime."""
    
    def __init__(self, container: Container, event_bus: EventBus, logger: AsyncLogger):
        self._container = container
        self._event_bus = event_bus
        self._logger = logger
        
        self._is_stopping = False
        self._lock = threading.Lock()
        
    @property
    def is_stopping(self) -> bool:
        with self._lock:
            return self._is_stopping
            
    def shutdown(self) -> None:
        """
        Executes the graceful shutdown sequence.
        """
        with self._lock:
            if self._is_stopping:
                return
            self._is_stopping = True
            
        self._logger.info("Initiating graceful shutdown sequence.")
        
        # 1. Publish SystemStopping
        self._event_bus.publish(Event(topic="system.stopping"))
        
        # 2 & 3. Stop accepting new work and drain (handled by subsystem implementations checking is_stopping, and EventBus shutdown)
        self._event_bus.shutdown()
        
        # 4 & 5. Dispose registered services
        self._container.dispose()
        
        # 6 & 7. Flush logs and exit cleanly
        self._logger.info("Resources released. Shutting down logger.")
        self._logger.shutdown()
