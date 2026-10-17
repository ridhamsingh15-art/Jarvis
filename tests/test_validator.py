"""Unit tests for the Validator."""

import unittest
from unittest.mock import MagicMock

from core.exceptions import ValidationError
from core.registry import Registry
from core.task import Task
from core.validator import Validator


class TestValidator(unittest.TestCase):
    def setUp(self):
        """Set up a mock registry and validator for testing."""
        from core.action_definition import ActionDefinition
        
        self.mock_registry = MagicMock(spec=Registry)
        self.validator = Validator(registry=self.mock_registry)
        
        # Configure mock registry behavior
        self.mock_registry.has_tool.side_effect = lambda tool_name: tool_name == "mock_tool"
        self.mock_registry.list_tools.return_value = ["mock_tool"]
        
        # Actions for mock_tool
        self.mock_registry.get_actions.return_value = {
            "do_something": ActionDefinition("do_something", "Does a thing.", ["target"]),
            "complex_action": ActionDefinition("complex_action", "Complex.", ["source", "dest"]),
            "no_args": ActionDefinition("no_args", "No args.", []),
        }

    def test_valid_task(self):
        """Test that a perfectly valid task passes without raising."""
        task = Task(tool="mock_tool", action="do_something", args={"target": "user1"})
        
        # Should not raise any exceptions
        result = self.validator.validate(task)
        self.assertIs(result, task)
        
    def test_valid_task_no_args(self):
        """Test that an action requiring no args passes when empty args provided."""
        task = Task(tool="mock_tool", action="no_args", args={})
        
        result = self.validator.validate(task)
        self.assertIs(result, task)

    def test_invalid_tool_raises_error(self):
        """Test that an unknown tool raises ValidationError."""
        task = Task(tool="unknown_tool", action="do_something")
        
        with self.assertRaises(ValidationError) as context:
            self.validator.validate(task)
        self.assertIn("Unknown tool: 'unknown_tool'", str(context.exception))

    def test_invalid_action_raises_error(self):
        """Test that an unknown action raises ValidationError."""
        task = Task(tool="mock_tool", action="unknown_action")
        
        with self.assertRaises(ValidationError) as context:
            self.validator.validate(task)
        self.assertIn("Unknown action: 'unknown_action'", str(context.exception))

    def test_missing_required_argument_raises_error(self):
        """Test that omitting a required argument raises ValidationError."""
        # 'complex_action' requires both 'source' and 'dest'
        task = Task(tool="mock_tool", action="complex_action", args={"source": "A"})
        
        with self.assertRaises(ValidationError) as context:
            self.validator.validate(task)
        self.assertIn("Missing required argument: 'dest'", str(context.exception))

    def test_unknown_argument_raises_error(self):
        """Test that providing an undocumented argument raises ValidationError."""
        task = Task(
            tool="mock_tool", 
            action="do_something", 
            args={"target": "user1", "extra": "invalid"}
        )
        
        with self.assertRaises(ValidationError) as context:
            self.validator.validate(task)
        self.assertIn("Unknown argument: 'extra'", str(context.exception))
        
    def test_none_argument_raises_error(self):
        """Test that providing None for an argument raises ValidationError."""
        task = Task(tool="mock_tool", action="do_something", args={"target": None})
        
        with self.assertRaises(ValidationError) as context:
            self.validator.validate(task)
        self.assertIn("Argument 'target' cannot be None", str(context.exception))
        
    def test_empty_string_argument_raises_error(self):
        """Test that providing an empty string for an argument raises ValidationError."""
        task = Task(tool="mock_tool", action="do_something", args={"target": "   "})
        
        with self.assertRaises(ValidationError) as context:
            self.validator.validate(task)
        self.assertIn("Argument 'target' cannot be an empty string", str(context.exception))


if __name__ == "__main__":
    unittest.main()
