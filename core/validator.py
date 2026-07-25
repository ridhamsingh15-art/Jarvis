"""
Validator — safety gate before task execution.

Checks that every Task references a known tool and a valid action
for that tool. Rejects anything unknown before it can reach the
Executor. Uses Registry methods exclusively — never accesses
internal data structures directly.
"""

import logging

from core.exceptions import ValidationError
from core.registry import Registry
from core.task import Task

logger = logging.getLogger(__name__)


class Validator:
    """Validates Task objects against the Registry."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def validate(self, task: Task) -> Task:
        """Validate that a task can be executed.

        Checks:
            1. Tool exists in the Registry
            2. Action exists for that tool
            3. Required arguments are present and valid

        Args:
            task: The Task to validate.

        Returns:
            The same Task, unchanged (for pipeline chaining).

        Raises:
            ValidationError: If validation fails.
        """
        self._validate_tool(task)
        self._validate_action(task)
        self._validate_arguments(task)

        logger.debug(
            "Validated: tool=%s action=%s",
            task.tool,
            task.action,
        )

        return task

    def _validate_tool(self, task: Task) -> None:
        """Check that the tool exists in the Registry.

        Raises:
            ValidationError: If the tool is not registered.
        """
        if not self._registry.has_tool(task.tool):
            available = ", ".join(self._registry.list_tools())

            raise ValidationError(
                f"Unknown tool: '{task.tool}'. "
                f"Available tools: [{available}]"
            )

    def _validate_action(self, task: Task) -> None:
        """Check that the action exists for the given tool.

        Raises:
            ValidationError: If the action is not valid for the tool.
        """
        actions = self._registry.get_actions(task.tool)

        if task.action not in actions:
            available = ", ".join(actions.keys())

            raise ValidationError(
                f"Unknown action: '{task.action}' for tool "
                f"'{task.tool}'. Available actions: [{available}]"
            )

    def _validate_arguments(self, task: Task) -> None:
        """Validate the arguments for the task's action.
        
        Uses the structured ActionDefinition to check:
        1. Reject None values
        2. Reject empty strings
        3. Reject missing required arguments
        4. Reject unknown arguments
        
        Raises:
            ValidationError: If any argument validation fails.
        """
        actions = self._registry.get_actions(task.tool)
        action_def = actions[task.action]

        expected_args = set(action_def.required_args + action_def.optional_args)

        # 1 & 2. Reject None and empty strings
        for key, value in task.args.items():
            if value is None:
                raise ValidationError(f"Argument '{key}' cannot be None.")
            if isinstance(value, str) and not value.strip():
                raise ValidationError(f"Argument '{key}' cannot be an empty string.")

        # 3. Missing required arguments
        for req in action_def.required_args:
            if req not in task.args:
                raise ValidationError(
                    f"Missing required argument: '{req}' for action '{task.action}'"
                )

        # 4. Unknown arguments
        for provided in task.args.keys():
            if provided not in expected_args:
                raise ValidationError(
                    f"Unknown argument: '{provided}' for action '{task.action}'"
                )