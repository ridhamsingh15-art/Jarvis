"""
Context propagation for logging.
Uses contextvars to support both threads and async execution contexts securely.
"""
from contextvars import ContextVar
from typing import Dict, Any, Optional

# Context variable to hold correlation IDs
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

# Context variable to hold component tags
_component_name: ContextVar[str] = ContextVar("component_name", default="System")

# Context variable to hold any additional structured metadata
_context_metadata: ContextVar[Dict[str, Any]] = ContextVar("context_metadata", default={})


def set_correlation_id(corr_id: str) -> None:
    """Set the correlation ID for the current execution context."""
    _correlation_id.set(corr_id)

def get_correlation_id() -> Optional[str]:
    """Retrieve the correlation ID for the current execution context."""
    return _correlation_id.get()

def set_component_name(name: str) -> None:
    """Set the active component name for the current execution context."""
    _component_name.set(name)

def get_component_name() -> str:
    """Retrieve the active component name for the current execution context."""
    return _component_name.get()

def add_metadata(key: str, value: Any) -> None:
    """Add a structured metadata key-value pair to the current context."""
    current = _context_metadata.get()
    # Create a new dict to avoid mutating the context var in place unintentionally across async yields
    new_meta = current.copy()
    new_meta[key] = value
    _context_metadata.set(new_meta)

def get_metadata() -> Dict[str, Any]:
    """Retrieve all structured metadata for the current context."""
    return _context_metadata.get().copy()

def clear_context() -> None:
    """Clear all logging context variables for the current execution context."""
    _correlation_id.set(None)
    _component_name.set("System")
    _context_metadata.set({})
