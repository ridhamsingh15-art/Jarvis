"""
Exceptions for the Self-Evolution Framework.
"""

class EvolutionError(Exception):
    """Base exception for the evolution subsystem."""

class ProposalValidationError(EvolutionError):
    """Raised when an invalid proposal is generated."""

class ApprovalRequiredError(EvolutionError):
    """Raised when the system attempts to implement unapproved changes."""

class MetricCollectionError(EvolutionError):
    """Raised when system metrics cannot be collected."""

class ProfilingError(EvolutionError):
    """Raised when architecture profiling fails."""
