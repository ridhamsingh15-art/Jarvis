"""
Universal return type for tool executions in Jarvis.

ExecutionResult is a pure, immutable data transfer object (DTO) that
represents the outcome of a tool execution. It contains no business logic
and is strictly used to communicate execution outcomes to downstream components.
"""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class ExecutionResult:
    """Immutable data model representing the outcome of a tool execution.

    Attributes:
        success: True if the execution completed successfully, False otherwise.
        duration: The time taken for the execution in seconds.
        output: The result payload from the tool. Can be of any type. Defaults to None.
        error: An Exception instance if the execution failed. Defaults to None.
        metadata: An immutable mapping containing execution context. Defaults to empty.
    """

    success: bool
    duration: float
    output: Any | None = None
    error: Exception | None = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        """Validate state and enforce immutability on mutable fields."""
        if self.duration < 0.0:
            raise ValueError("duration cannot be negative")

        # Ensure metadata is an immutable MappingProxyType
        if not isinstance(self.metadata, MappingProxyType):
            # Using object.__setattr__ to bypass the frozen dataclass constraint
            # during initialization.
            object.__setattr__(
                self, "metadata", MappingProxyType(dict(self.metadata))
            )
