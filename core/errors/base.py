import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

from core.telemetry.context import get_component_name, get_correlation_id

from .enums import ErrorCategory, ErrorSeverity


class JarvisError(Exception):
    """
    The canonical base exception for the entire JARVIS AIOS.
    Captures strict context, stack traces, and metadata upon instantiation.
    """
    
    # Defaults meant to be overridden by subclasses
    category: ErrorCategory = ErrorCategory.UNKNOWN
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    retryable: bool = False
    recoverable: bool = False

    def __init__(
        self, 
        message: str, 
        root_cause: Exception | None = None,
        metadata: dict[str, Any] | None = None
    ):
        super().__init__(message)
        
        # Unique identifier for tracking this exact instance of failure
        self.error_id = str(uuid.uuid4())
        
        # When exactly it happened
        self.timestamp = datetime.now(timezone.utc).isoformat()
        
        self.message = message
        self.root_cause = root_cause
        self.metadata = metadata or {}
        
        # Environment context injection
        self.correlation_id = get_correlation_id()
        self.component = get_component_name()
        
        # Capture current stack trace immediately
        # Drop the first frame so we don't just see the __init__ call
        stack = traceback.extract_stack()[:-1]
        self.stack_trace = "".join(traceback.format_list(stack))
        
        # If the root cause is another Exception, capture its traceback if it has one
        if root_cause and not isinstance(root_cause, JarvisError):
            if getattr(root_cause, "__traceback__", None):
                self.stack_trace += f"\nCaused by {type(root_cause).__name__}: {root_cause!s}\n"
                self.stack_trace += "".join(traceback.format_tb(root_cause.__traceback__))
            else:
                self.stack_trace += f"\nCaused by: {root_cause!r}"

    def to_dict(self) -> dict[str, Any]:
        """
        Deep serialization for integration with the Logging module.
        """
        payload = {
            "error_id": self.error_id,
            "timestamp": self.timestamp,
            "category": self.category.value,
            "severity": self.severity.value,
            "component": self.component,
            "correlation_id": self.correlation_id,
            "message": self.message,
            "retryable": self.retryable,
            "recoverable": self.recoverable,
            "metadata": self.metadata,
            "stack_trace": self.stack_trace
        }
        
        if self.root_cause:
            if isinstance(self.root_cause, JarvisError):
                payload["root_cause"] = self.root_cause.to_dict()
            else:
                payload["root_cause"] = {
                    "type": type(self.root_cause).__name__,
                    "message": str(self.root_cause)
                }
                
        return payload

    def __str__(self) -> str:
        return f"[{self.category.value}] {self.message} (ID: {self.error_id})"
