"""
Runtime interfaces for JARVIS AIOS.

This module defines the abstract protocols and base classes that all
OS subsystems must implement to integrate with the Runtime Kernel.
"""

from abc import ABC, abstractmethod

from .enums import ComponentState
from .models import ComponentMetadata, HealthReport


class RuntimeComponent(ABC):
    """
    Abstract Base Class defining the lifecycle contract for all JARVIS subsystems.
    
    Any subsystem (Memory, Planner, Executor) must implement this interface
    to be registered and orchestrated by the OS runtime kernel.
    """

    @property
    @abstractmethod
    def metadata(self) -> ComponentMetadata:
        """
        Returns the static metadata defining this component.
        """

    @property
    @abstractmethod
    def state(self) -> ComponentState:
        """
        Returns the current lifecycle state of the component.
        """

    @abstractmethod
    async def start(self) -> None:
        """
        Initializes the component.
        
        This method should allocate required resources, establish database
        connections, and spawn background tasks.
        
        Raises:
            ComponentLifecycleError: If the component is already running.
        """

    @abstractmethod
    async def stop(self) -> None:
        """
        Gracefully terminates the component.
        
        This method must flush buffers, close connections, and release
        resources cleanly.
        
        Raises:
            ComponentLifecycleError: If the component is not currently running.
        """

    @abstractmethod
    async def health(self) -> HealthReport:
        """
        Generates a diagnostic health report for this specific component.
        
        This is periodically polled by the OS kernel to detect degraded systems
        and trigger auto-recovery or failover logic.
        """
