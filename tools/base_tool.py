"""
Abstract base class defining the contract for all Jarvis tools.

Every tool must implement this interface. The Registry only
accepts BaseTool instances, ensuring a consistent contract
across all current and future tools.
"""

from abc import ABC, abstractmethod
from typing import Any

from core.action_definition import ActionDefinition


class BaseTool(ABC):
    """Contract that every JARVIS tool must fulfill."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this tool (e.g. 'windows')."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for LLM prompt generation."""

    @abstractmethod
    def get_actions(self) -> dict[str, ActionDefinition]:
        """Return available actions and their structured definitions."""

    def validate_action_call(
        self,
        action: object,
        args: object,
        *,
        aliases: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Validate the common action/argument envelope before tool dispatch.

        This is defense in depth for direct tool callers; the canonical Validator
        remains responsible for checking model-generated Tasks before execution.
        """
        from core.exceptions import ExecutionError

        if not isinstance(action, str) or not action.strip():
            raise ExecutionError("Action name must be a non-empty string.")
        if not isinstance(args, dict):
            raise ExecutionError("Tool arguments must be a JSON object.")

        canonical_action = (aliases or {}).get(action, action)
        definition = self.get_actions().get(canonical_action)
        if definition is None:
            raise ExecutionError(f"Unknown {self.name} action: '{action}'.")

        if any(not isinstance(key, str) for key in args):
            raise ExecutionError("Tool argument names must be strings.")

        allowed = set(definition.required_args) | set(definition.optional_args)
        unknown = set(args) - allowed
        if unknown:
            raise ExecutionError(f"Unknown argument(s) for {self.name}.{canonical_action}: {sorted(unknown)}.")

        missing = [key for key in definition.required_args if key not in args]
        if missing:
            raise ExecutionError(
                f"Missing required argument(s) for {self.name}.{canonical_action}: {missing}."
            )
        return args

    @abstractmethod
    def execute(self, action: str, args: dict) -> str:
        """Execute a validated action with the given arguments."""
