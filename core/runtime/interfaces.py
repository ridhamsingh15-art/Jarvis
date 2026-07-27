from typing import Protocol, runtime_checkable
from .models import ComponentMetadata, HealthReport
from .enums import RuntimeState

@runtime_checkable
class RuntimeComponent(Protocol):
    """
    Protocol that all JARVIS AIOS runtime components must implement.
    """
    def start(self) -> None:
        """Initialize and start the component."""
        ...

    def stop(self) -> None:
        """Gracefully stop the component."""
        ...

    def health(self) -> HealthReport:
        """Return the current health status of the component."""
        ...

    def metadata(self) -> ComponentMetadata:
        """Return the component's metadata."""
        ...
