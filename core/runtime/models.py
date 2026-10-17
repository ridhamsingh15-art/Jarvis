"""
Runtime data models for JARVIS AIOS.

This module defines the immutable data models used by the runtime
subsystem to represent component metadata and health diagnostics.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .enums import HealthState


@dataclass(frozen=True)
class ComponentMetadata:
    """
    Immutable metadata describing a registered runtime component.
    
    Attributes:
        id: Unique identifier for the component (e.g., 'core.memory').
        name: Human-readable name of the component.
        version: Semantic version string.
        dependencies: List of component IDs this component requires to start.
    """
    id: str
    name: str
    version: str
    dependencies: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HealthReport:
    """
    Represents an immutable snapshot of a component's operational health.
    
    Attributes:
        component_id: The ID of the component generating this report.
        state: The overall health classification.
        timestamp: UTC time when the report was generated.
        details: Optional dictionary containing arbitrary diagnostic metrics.
        error: Optional string describing the failure reason if unhealthy.
    """
    component_id: str
    state: HealthState
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class HeartbeatPayload:
    """Payload for runtime heartbeats."""
    component_id: str
    status: HealthState
    state: str
    active_components: int
    uptime_seconds: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "status": self.status.value,
            "state": self.state,
            "active_components": self.active_components,
            "uptime_seconds": self.uptime_seconds,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass(frozen=True)
class StateChangePayload:
    """Payload for runtime state changes."""
    component_id: str
    old_state: str
    new_state: str
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
