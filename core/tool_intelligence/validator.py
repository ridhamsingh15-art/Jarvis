"""
Intelligence Validation — wraps the strict core Validator.
"""

from core.exceptions import JarvisError
from core.task import Task
from core.tool_intelligence.models import IntelligenceOutcome, RepairMetrics
from core.validator import Validator


class IntelligenceValidator:
    """Safely runs the repaired Task through the core Validator."""

    def __init__(self, core_validator: Validator) -> None:
        self._validator = core_validator

    def validate(self, task: Task, metrics: RepairMetrics) -> IntelligenceOutcome:
        """Validate the task and return a structured outcome instead of raising.

        Args:
            task: The (potentially repaired) Task.
            metrics: The repair metrics gathered during the repair pipeline.

        Returns:
            An IntelligenceOutcome encapsulating success or failure.
        """
        try:
            self._validator.validate(task)
            return IntelligenceOutcome(
                task=task,
                is_valid=True,
                metrics=metrics,
            )
        except JarvisError as exc:
            return IntelligenceOutcome(
                task=task,
                is_valid=False,
                metrics=metrics,
                error_message=str(exc),
            )
