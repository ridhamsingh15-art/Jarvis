class PluginError(Exception):
    """Base exception for the plugin runtime subsystem."""

class PluginLoadError(PluginError):
    """Raised when a plugin fails to load."""

class PluginValidationError(PluginError):
    """Raised when a plugin's manifest or structure is invalid."""

class PluginLifecycleError(PluginError):
    """Raised during invalid lifecycle transitions or failures during lifecycle hooks."""

class PluginDependencyError(PluginError):
    """Raised when dependencies cannot be resolved or have cycles."""

class PluginSecurityError(PluginError):
    """Raised when a plugin violates sandbox or security policies."""
