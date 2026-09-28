"""
Exceptions for the Federation subsystem.
"""

class FederationError(Exception):
    """Base exception for the Federation subsystem."""

class NodeOfflineError(FederationError):
    """Raised when attempting to communicate with an offline node."""

class FederationAuthError(FederationError):
    """Raised when node authentication or trust validation fails."""

class DelegationFailedError(FederationError):
    """Raised when a mission cannot be successfully delegated to a remote node."""

class StateSyncError(FederationError):
    """Raised when synchronizing state across the federation fails."""

class DiscoveryError(FederationError):
    """Raised during node discovery failures."""
