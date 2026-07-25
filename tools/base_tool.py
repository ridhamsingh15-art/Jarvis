"""
Abstract base class defining the contract for all Jarvis tools.

Every tool must implement this interface. The Registry only
accepts BaseTool instances, ensuring a consistent contract
across all current and future tools.
"""

from abc import ABC, abstractmethod

from core.action_definition import ActionDefinition


class BaseTool(ABC):
    """Contract that every Jarvis tool must fulfill."""

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
        """Return available actions and their structured definitions.

        Returns:
            Dict mapping action names to ActionDefinition objects.
        """

    @abstractmethod
    def execute(self, action: str, args: dict) -> str:
        """Execute a validated action with the given arguments.

        Args:
            action: The action to perform (must be in get_actions()).
            args: Dictionary of arguments for the action.

        Returns:
            Human-readable result string.

        Raises:
            ExecutionError: If the action fails.
        """
