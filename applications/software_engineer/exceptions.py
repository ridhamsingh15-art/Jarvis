"""
Exceptions for the Autonomous Software Engineering Framework.
"""

class SoftwareEngineeringError(Exception):
    """Base exception for the software engineering framework."""

class GitConflictError(SoftwareEngineeringError):
    """Raised when an automated git operation encounters a conflict or failure."""

class ArchitectureViolationError(SoftwareEngineeringError):
    """Raised when generated code violates established architectural patterns."""

class TestFailureError(SoftwareEngineeringError):
    """Raised when automated tests fail after implementation or refactoring."""

class SecurityViolationError(SoftwareEngineeringError):
    """Raised when the security reviewer detects an unsafe operation."""

class ReviewRejectionError(SoftwareEngineeringError):
    """Raised when the code reviewer rejects an implementation."""

class QualityGateError(SoftwareEngineeringError):
    """Raised when a quality gate (like mandatory checkpoints) is bypassed."""
