"""
Tool registry — single source of truth for available tools.

The Registry holds all registered BaseTool instances and provides
lookup, validation, and description generation. The Planner uses
describe() to dynamically build LLM prompts, so tools are never
hardcoded in prompts.
"""

import logging
from typing import Optional

from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class Registry:
    """Manages tool registration, lookup, and description generation."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance.

        Args:
            tool: A BaseTool implementation to register.

        Raises:
            TypeError: If tool is not a BaseTool instance.
            ValueError: If a tool with the same name is already registered.
        """
        if not isinstance(tool, BaseTool):
            raise TypeError(
                f"Expected BaseTool instance, got {type(tool).__name__}"
            )

        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")

        self._tools[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered by name."""
        return name in self._tools

    def get_executor(self, name: str) -> Optional[BaseTool]:
        """Get the tool instance for execution.

        Args:
            name: Tool name.

        Returns:
            The BaseTool instance, or None if not found.
        """
        return self._tools.get(name)

    def get_actions(self, name: str) -> dict[str, str]:
        """Get available actions for a tool.

        Args:
            name: Tool name.

        Returns:
            Dict of action names to descriptions, or empty dict
            if tool not found.
        """
        tool = self._tools.get(name)

        if tool is None:
            return {}

        return tool.get_actions()

    def list_tools(self) -> list[str]:
        """Return names of all registered tools."""
        return list(self._tools.keys())

    def describe(self) -> str:
        """Generate a structured description of all tools for the LLM.

        Returns:
            Formatted string describing every tool and its actions.
        """
        if not self._tools:
            return "No tools available."

        sections: list[str] = []

        for tool in self._tools.values():
            lines = [
                f"Tool: {tool.name}",
                f"Description: {tool.description}",
                "Actions:",
            ]

            for action_name, action_desc in tool.get_actions().items():
                lines.append(f"  - {action_name}: {action_desc}")

            sections.append("\n".join(lines))

        return "\n\n".join(sections)