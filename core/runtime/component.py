"""
State and lifecycle tracking utilities for Runtime components.

This module provides composition-based utilities to help implement
the RuntimeComponent interface without forcing deep inheritance hierarchies.
"""

import threading
from collections.abc import Awaitable, Callable

from .enums import ComponentState, HealthState
from .exceptions import ComponentLifecycleError
from .interfaces import RuntimeComponent
from .models import ComponentMetadata, HealthReport


class ComponentStateTracker:
    """
    Thread-safe tracker for component lifecycle states.

    Composition over inheritance: Components should instantiate this tracker
    internally rather than inheriting from a base class to manage their
    standard OS lifecycle transitions safely.
    """

    def __init__(self, metadata: ComponentMetadata) -> None:
        self._metadata = metadata
        self._state = ComponentState.INITIALIZED
        self._lock = threading.RLock()

    @property
    def state(self) -> ComponentState:
        """Returns the current state in a thread-safe manner."""
        with self._lock:
            return self._state

    async def execute_start(self, start_func: Callable[[], Awaitable[None]]) -> None:
        """
        Safely executes the provided start function, managing state transitions.
        """
        with self._lock:
            if self._state in (ComponentState.RUNNING, ComponentState.STARTING):
                raise ComponentLifecycleError(
                    f"Component {self._metadata.id} is already {self._state}."
                )
            self._state = ComponentState.STARTING

        try:
            await start_func()
            with self._lock:
                self._state = ComponentState.RUNNING
        except Exception as e:
            with self._lock:
                self._state = ComponentState.FAILED
            raise ComponentLifecycleError(
                f"Failed to start {self._metadata.id}: {e}"
            ) from e

    async def execute_stop(self, stop_func: Callable[[], Awaitable[None]]) -> None:
        """
        Safely executes the provided stop function, managing state transitions.
        """
        with self._lock:
            if self._state != ComponentState.RUNNING:
                raise ComponentLifecycleError(
                    f"Component {self._metadata.id} is not running."
                )
            self._state = ComponentState.STOPPING

        try:
            await stop_func()
            with self._lock:
                self._state = ComponentState.STOPPED
        except Exception as e:
            with self._lock:
                self._state = ComponentState.FAILED
            raise ComponentLifecycleError(
                f"Failed to stop {self._metadata.id}: {e}"
            ) from e

    def generate_health(self) -> HealthReport:
        """Generates a default health report based on the current state."""
        with self._lock:
            if self._state == ComponentState.RUNNING:
                return HealthReport(
                    component_id=self._metadata.id,
                    state=HealthState.HEALTHY
                )
            return HealthReport(
                component_id=self._metadata.id,
                state=HealthState.UNKNOWN,
                error=f"Component is not running. Current state: {self._state}"
            )


from abc import abstractmethod


class BaseComponent(RuntimeComponent):
    """
    Legacy abstract base component preserved for backward compatibility.
    """
    def __init__(self, metadata: ComponentMetadata) -> None:
        self.tracker = ComponentStateTracker(metadata)
        
    @property
    def metadata(self) -> ComponentMetadata:
        return self.tracker._metadata
        
    @property
    def state(self) -> ComponentState:
        return self.tracker.state
        
    async def start(self) -> None:
        await self.tracker.execute_start(self._do_start)
        
    async def stop(self) -> None:
        await self.tracker.execute_stop(self._do_stop)
        
    async def health(self) -> HealthReport:
        return self.tracker.generate_health()
        
    @abstractmethod
    async def _do_start(self) -> None:
        pass
        
    @abstractmethod
    async def _do_stop(self) -> None:
        pass
