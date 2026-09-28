"""
Data models for the Tool Intelligence subsystem.
"""

from dataclasses import dataclass, field

from core.task import Task


@dataclass(frozen=True)
class RepairMetrics:
    """Statistics about a repair operation."""
    
    tool_name_repaired: bool = False
    action_name_repaired: bool = False
    arguments_repaired: int = 0
    total_arguments: int = 0
    
    @property
    def was_repaired(self) -> bool:
        """Return True if any part of the payload was repaired."""
        return self.tool_name_repaired or self.action_name_repaired or self.arguments_repaired > 0


@dataclass(frozen=True)
class IntelligenceOutcome:
    """The result of passing a Task through the intelligence pipeline."""
    
    task: Task
    is_valid: bool
    metrics: RepairMetrics = field(default_factory=RepairMetrics)
    error_message: str | None = None
