"""
Tool registry — single source of truth for available tools.

The Registry holds all registered BaseTool instances and provides
lookup, validation, and description generation. The Planner uses
describe() to dynamically build LLM prompts, so tools are never
hardcoded in prompts.
"""

import logging
import threading
from typing import Any, Optional

from core.action_definition import ActionDefinition
from core.exceptions import ToolRegistrationError, ToolNotFoundError
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class Registry:
    """Manages tool registration, lookup, and description generation."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._lock = threading.RLock()

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance.

        Args:
            tool: A BaseTool implementation to register.

        Raises:
            ToolRegistrationError: If tool is None, not a BaseTool instance, or already registered.
        """
        if tool is None:
            raise ToolRegistrationError("Cannot register a None tool.")

        if not isinstance(tool, BaseTool):
            raise ToolRegistrationError(
                f"Expected BaseTool instance, got {type(tool).__name__}"
            )

        with self._lock:
            if tool.name in self._tools:
                raise ToolRegistrationError(f"Tool already registered: {tool.name}")

            self._tools[tool.name] = tool
            logger.info("Registered tool: %s", tool.name)

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry.

        Args:
            name: The name of the tool to remove.

        Raises:
            ToolNotFoundError: If the tool is not registered.
        """
        with self._lock:
            if name not in self._tools:
                raise ToolNotFoundError(f"Cannot unregister. Tool '{name}' not found.")

            del self._tools[name]
            logger.info("Unregistered tool: %s", name)

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered by name."""
        with self._lock:
            return name in self._tools

    def exists(self, name: str) -> bool:
        """Check if a tool is registered by name. Alias for has_tool."""
        return self.has_tool(name)

    def get(self, name: str) -> Optional[BaseTool]:
        """Get the tool instance for execution.

        Args:
            name: Tool name.

        Returns:
            The BaseTool instance, or None if not found.
        """
        with self._lock:
            return self._tools.get(name)

    def get_executor(self, name: str) -> Optional[BaseTool]:
        """Alias for get(name) to preserve backward compatibility."""
        return self.get(name)

    def get_actions(self, name: str) -> dict[str, ActionDefinition]:
        """Get available actions for a tool.

        Args:
            name: Tool name.

        Returns:
            Dict of action names to ActionDefinitions, or empty dict
            if tool not found.
        """
        tool = self.get(name)

        if tool is None:
            return {}

        return tool.get_actions()

    def list_tools(self) -> list[str]:
        """Return names of all registered tools."""
        with self._lock:
            return list(self._tools.keys())

    def metadata(self, name: str) -> dict[str, Any]:
        """Retrieve metadata for a registered tool.

        Args:
            name: The name of the tool.

        Returns:
            A dictionary containing the tool's name, description, and available actions.

        Raises:
            ToolNotFoundError: If the tool does not exist in the registry.
        """
        tool = self.get(name)
        if tool is None:
            raise ToolNotFoundError(f"Tool '{name}' not found.")
            
        return {
            "name": tool.name,
            "description": tool.description,
            "actions": tool.get_actions(),
        }

    def clear(self) -> None:
        """Remove all tools from the registry."""
        with self._lock:
            count = len(self._tools)
            self._tools.clear()
            logger.info("Cleared %d tools from the registry.", count)

    def describe(self) -> str:
        """Generate a structured description of all tools for the LLM.

        Returns:
            Formatted string describing every tool and its actions.
        """
        with self._lock:
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