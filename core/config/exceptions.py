"""
Exceptions for the Configuration module.
"""

class ConfigurationError(Exception):
    """Base exception for all configuration related errors."""

class SchemaValidationError(ConfigurationError):
    """Raised when configuration validation against the schema fails."""

class MissingConfigurationError(ConfigurationError):
    """Raised when a required configuration key is missing."""
