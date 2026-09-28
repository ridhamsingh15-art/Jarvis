"""
Runtime enumerations for JARVIS AIOS.

This module defines the core enumerations used throughout the runtime
subsystem, including component lifecycle states, health statuses, and
system-level lifecycle events.
"""

from enum import StrEnum


class ComponentState(StrEnum):
    """
    Represents the lifecycle state of a RuntimeComponent.

    The state machine strictly governs how a component transitions
    from initialization through execution and eventual shutdown.
    """
    INITIALIZED = "INITIALIZED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class RuntimeState(StrEnum):
    """
    Represents the overarching lifecycle state of the entire OS Runtime.
    """
    INITIALIZED = "INITIALIZED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class HealthState(StrEnum):
    """
    Represents the operational health status of a RuntimeComponent or the OS.

    Used by the HealthMonitor to determine if the system is operating
    optimally, experiencing latency/errors, or critically failing.
    """
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class LifecycleEvent(StrEnum):
    """
    Represents standardized event topics emitted by the Runtime subsystem.

    These topics are broadcasted over the EventBus to notify other
    subsystems of critical OS-level lifecycle changes.
    """
    BOOT_STARTED = "runtime.boot.started"
    BOOT_COMPLETED = "runtime.boot.completed"
    SHUTDOWN_STARTED = "runtime.shutdown.started"
    SHUTDOWN_COMPLETED = "runtime.shutdown.completed"
    COMPONENT_REGISTERED = "runtime.component.registered"
    COMPONENT_STARTED = "runtime.component.started"
    COMPONENT_STOPPED = "runtime.component.stopped"
    COMPONENT_FAILED = "runtime.component.failed"
    HEALTH_DEGRADED = "runtime.health.degraded"
    HEALTH_RECOVERED = "runtime.health.recovered"
