"""
JARVIS AIOS Runtime

The central runtime coordinator mapping component lifecycles, health checks, 
and background heartbeats directly onto the Foundation orchestrator.
"""

from .component import BaseComponent, ComponentStateTracker
from .enums import ComponentState, HealthState, LifecycleEvent, RuntimeState
from .exceptions import (
    ComponentLifecycleError,
    ComponentNotFoundError,
    ComponentRegistrationError,
    ComponentResolutionError,
    RuntimeError,
)
from .health import HealthMonitor
from .heartbeat import HeartbeatService
from .interfaces import RuntimeComponent
from .kernel import RuntimeKernel
from .models import (
    ComponentMetadata,
    HealthReport,
    HeartbeatPayload,
    StateChangePayload,
)
from .registry import ComponentRegistry as RuntimeRegistry

__all__ = [
    "BaseComponent",
    "ComponentLifecycleError",
    "ComponentMetadata",
    "ComponentNotFoundError",
    "ComponentRegistrationError",
    "ComponentResolutionError",
    "ComponentState",
    "ComponentStateTracker",
    "HealthMonitor",
    "HealthReport",
    "HealthState",
    "HeartbeatPayload",
    "HeartbeatService",
    "LifecycleEvent",
    "RuntimeComponent",
    "RuntimeError",
    "RuntimeKernel",
    "RuntimeRegistry",
    "RuntimeState",
    "StateChangePayload"
]
