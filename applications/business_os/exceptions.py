"""
Exceptions for the Autonomous Business Operating System.
"""

class BusinessOSError(Exception):
    """Base exception for BusinessOS errors."""

class FinancialConstraintError(BusinessOSError):
    """Raised when an operation attempts to perform unapproved financial transactions."""

class DelegationError(BusinessOSError):
    """Raised when an operation fails to delegate to the appropriate subsystem."""

class PlanningError(BusinessOSError):
    """Raised when the planner fails to generate a viable business plan."""

class AnalyticsError(BusinessOSError):
    """Raised when raw data cannot be parsed into KPIs."""
