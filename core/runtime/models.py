from dataclasses import dataclass, field
from typing import Dict, Any, List
from core.models import JarvisModel, Timestamp

from .enums import RuntimeState

@dataclass(frozen=True, slots=True)
class ComponentMetadata(JarvisModel):
    """Metadata describing a runtime component."""
    name: str
    version: str
    description: str = ""
    dependencies: List[str] = field(default_factory=list)

@dataclass(frozen=True, slots=True)
class HealthReport(JarvisModel):
    """A standard health status snapshot."""
    is_healthy: bool
    status: str
    component_name: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: Timestamp = field(default_factory=Timestamp)

@dataclass(frozen=True, slots=True)
class HeartbeatPayload(JarvisModel):
    """Data payload for heartbeat events."""
    uptime_seconds: float
    state: RuntimeState
    active_components: int
    health_status: str

@dataclass(frozen=True, slots=True)
class StateChangePayload(JarvisModel):
    """Data payload when state transitions occur."""
    old_state: RuntimeState
    new_state: RuntimeState
    reason: str = ""
