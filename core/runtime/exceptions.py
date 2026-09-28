"""
Runtime exceptions for JARVIS AIOS.

This module defines the domain-specific exception hierarchy for the
runtime subsystem, ensuring standardized error handling across the OS.
"""


class RuntimeError(Exception):
    """Base exception class for all Runtime subsystem errors."""


class ComponentRegistrationError(RuntimeError):
    """
    Raised when a component cannot be registered with the Runtime.
    
    This typically occurs if a duplicate component ID is detected or if
    a component fails validation checks during boot.
    """


class ComponentNotFoundError(RuntimeError):
    """
    Raised when a requested component does not exist in the registry.
    """


class ComponentLifecycleError(RuntimeError):
    """
    Raised when an invalid state transition is attempted.
    
    Examples include attempting to start an already running component,
    or attempting to stop an already stopped component.
    """

class ComponentResolutionError(RuntimeError):
    """Raised when component dependencies cannot be resolved (e.g. cycles or missing)."""
