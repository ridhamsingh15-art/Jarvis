"""
Schema resolver — extracts expected schemas from the Tool Registry.
"""

from typing import cast

from core.action_definition import ActionDefinition
from core.registry import Registry
from core.tool_intelligence.exceptions import SchemaResolutionError


class SchemaResolver:
    """Retrieves tool schemas to inform the intelligence layer."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def get_action_schema(self, tool_name: str, action_name: str) -> ActionDefinition:
        """Retrieve the ActionDefinition for a specific tool and action.

        Args:
            tool_name: The resolved tool name.
            action_name: The resolved action name.

        Returns:
            The ActionDefinition instance.

        Raises:
            SchemaResolutionError: If the tool or action does not exist.
        """
        if not self._registry.has_tool(tool_name):
            raise SchemaResolutionError(f"Tool '{tool_name}' not found in registry.")

        actions = self._registry.get_actions(tool_name)
        if action_name not in actions:
            raise SchemaResolutionError(
                f"Action '{action_name}' not found on tool '{tool_name}'."
            )

        return cast(ActionDefinition, actions[action_name])
