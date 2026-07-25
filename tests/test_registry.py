"""Unit tests for the Registry."""

import unittest
from unittest.mock import MagicMock

from core.exceptions import ToolNotFoundError, ToolRegistrationError
from core.registry import Registry
from tools.base_tool import BaseTool
from core.action_definition import ActionDefinition


class MockTool(BaseTool):
    """A mock implementation of BaseTool for testing."""

    def __init__(self, name: str = "mock_tool", description: str = "A test tool."):
        self._name = name
        self._description = description
        self._actions = {
            "mock_action": ActionDefinition(
                name="mock_action",
                description="Does a mock thing.",
                required_args=[]
            )
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    def get_actions(self) -> dict[str, ActionDefinition]:
        return self._actions

    def execute(self, action: str, args: dict) -> str:
        return f"Executed {action}"


class TestRegistry(unittest.TestCase):
    def setUp(self):
        """Initialize a fresh Registry before each test."""
        self.registry = Registry()
        self.tool1 = MockTool("tool1", "Description for tool 1")
        self.tool2 = MockTool("tool2", "Description for tool 2")

    def test_register_successful(self):
        """Test that a valid tool is registered correctly."""
        self.registry.register(self.tool1)
        self.assertTrue(self.registry.has_tool("tool1"))
        self.assertEqual(self.registry.get_executor("tool1"), self.tool1)

    def test_register_duplicate_raises_error(self):
        """Test that registering a tool with an existing name raises an error."""
        self.registry.register(self.tool1)
        
        duplicate_tool = MockTool("tool1", "Different description")
        with self.assertRaises(ToolRegistrationError) as context:
            self.registry.register(duplicate_tool)
        self.assertIn("already registered", str(context.exception))

    def test_register_invalid_type_raises_error(self):
        """Test that registering an object that isn't a BaseTool raises an error."""
        class NotATool:
            name = "fake_tool"

        with self.assertRaises(ToolRegistrationError) as context:
            self.registry.register(NotATool()) # type: ignore
        self.assertIn("Expected BaseTool instance", str(context.exception))

    def test_register_none_raises_error(self):
        """Test that registering None raises an error."""
        with self.assertRaises(ToolRegistrationError) as context:
            self.registry.register(None) # type: ignore
        self.assertIn("Cannot register a None tool", str(context.exception))

    def test_unregister_successful(self):
        """Test that a registered tool can be unregistered."""
        self.registry.register(self.tool1)
        self.assertTrue(self.registry.exists("tool1"))
        
        self.registry.unregister("tool1")
        self.assertFalse(self.registry.exists("tool1"))

    def test_unregister_nonexistent_raises_error(self):
        """Test that unregistering a non-existent tool raises an error."""
        with self.assertRaises(ToolNotFoundError) as context:
            self.registry.unregister("missing_tool")
        self.assertIn("not found", str(context.exception))

    def test_get_successful(self):
        """Test retrieving a registered tool via get() and get_executor()."""
        self.registry.register(self.tool1)
        retrieved_get = self.registry.get("tool1")
        retrieved_exec = self.registry.get_executor("tool1")
        
        self.assertIs(retrieved_get, self.tool1)
        self.assertIs(retrieved_exec, self.tool1)

    def test_get_nonexistent_returns_none(self):
        """Test retrieving a missing tool returns None (preserves behavior)."""
        self.assertIsNone(self.registry.get("missing_tool"))
        self.assertIsNone(self.registry.get_executor("missing_tool"))

    def test_exists_and_has_tool(self):
        """Test checking if a tool exists with both method names."""
        self.assertFalse(self.registry.has_tool("tool1"))
        self.assertFalse(self.registry.exists("tool1"))
        
        self.registry.register(self.tool1)
        
        self.assertTrue(self.registry.has_tool("tool1"))
        self.assertTrue(self.registry.exists("tool1"))

    def test_list_tools(self):
        """Test listing all registered tools."""
        self.assertEqual(self.registry.list_tools(), [])
        
        self.registry.register(self.tool1)
        self.assertEqual(self.registry.list_tools(), ["tool1"])
        
        self.registry.register(self.tool2)
        self.assertCountEqual(self.registry.list_tools(), ["tool1", "tool2"])

    def test_get_actions(self):
        """Test getting actions for a tool."""
        self.registry.register(self.tool1)
        self.assertEqual(self.registry.get_actions("tool1"), self.tool1.get_actions())
        
        # Test non-existent tool returns empty dict
        self.assertEqual(self.registry.get_actions("missing"), {})

    def test_describe(self):
        """Test generating descriptions for LLM."""
        self.assertEqual(self.registry.describe(), "No tools available.")
        
        self.registry.register(self.tool1)
        description = self.registry.describe()
        self.assertIn("Tool: tool1", description)
        self.assertIn("Description for tool 1", description)
        self.assertIn("mock_action", description)

    def test_metadata_successful(self):
        """Test retrieving metadata for a registered tool."""
        self.registry.register(self.tool1)
        meta = self.registry.metadata("tool1")
        
        self.assertEqual(meta["name"], "tool1")
        self.assertEqual(meta["description"], "Description for tool 1")
        self.assertEqual(meta["actions"], self.tool1.get_actions())

    def test_metadata_nonexistent_raises_error(self):
        """Test retrieving metadata for a missing tool raises an error."""
        with self.assertRaises(ToolNotFoundError):
            self.registry.metadata("missing_tool")

    def test_clear(self):
        """Test clearing all registered tools."""
        self.registry.register(self.tool1)
        self.registry.register(self.tool2)
        self.assertEqual(len(self.registry.list_tools()), 2)
        
        self.registry.clear()
        self.assertEqual(len(self.registry.list_tools()), 0)


if __name__ == '__main__':
    unittest.main()
