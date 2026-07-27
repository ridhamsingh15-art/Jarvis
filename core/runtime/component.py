from .interfaces import RuntimeComponent
from .models import ComponentMetadata, HealthReport
from .enums import RuntimeState

class BaseComponent(RuntimeComponent):
    """
    Abstract base class providing default component behavior.
    """
    def __init__(self, name: str, version: str = "1.0.0"):
        self._name = name
        self._version = version
        self._state = RuntimeState.STOPPED
        self._error = None

    def start(self) -> None:
        self._state = RuntimeState.RUNNING
        self._error = None

    def stop(self) -> None:
        self._state = RuntimeState.STOPPED

    def health(self) -> HealthReport:
        return HealthReport(
            is_healthy=(self._state == RuntimeState.RUNNING),
            status=self._state.value,
            component_name=self._name,
            details={"error": str(self._error)} if self._error else {}
        )

    def metadata(self) -> ComponentMetadata:
        return ComponentMetadata(
            name=self._name,
            version=self._version
        )
