"""Unit tests for ExecutionResult."""

import unittest
from dataclasses import FrozenInstanceError
from types import MappingProxyType

from core.execution_result import ExecutionResult


class TestExecutionResult(unittest.TestCase):
    def test_construction_and_defaults(self):
        """Test basic construction and default values."""
        result = ExecutionResult(success=True, duration=1.5)
        
        self.assertTrue(result.success)
        self.assertEqual(result.duration, 1.5)
        self.assertIsNone(result.output)
        self.assertIsNone(result.error)
        self.assertEqual(result.metadata, {})
        self.assertIsInstance(result.metadata, MappingProxyType)

    def test_construction_with_all_fields(self):
        """Test construction with all fields provided explicitly."""
        custom_error = RuntimeError("Test error")
        result = ExecutionResult(
            success=False,
            duration=0.5,
            output="Some partial output",
            error=custom_error,
            metadata={"key": "value"}
        )
        
        self.assertFalse(result.success)
        self.assertEqual(result.duration, 0.5)
        self.assertEqual(result.output, "Some partial output")
        self.assertIs(result.error, custom_error)
        self.assertEqual(result.metadata, {"key": "value"})
        self.assertIsInstance(result.metadata, MappingProxyType)

    def test_negative_duration_raises_error(self):
        """Test that a negative duration raises a ValueError."""
        with self.assertRaises(ValueError) as context:
            ExecutionResult(success=True, duration=-0.1)
        self.assertIn("duration cannot be negative", str(context.exception))

    def test_immutability_of_dataclass(self):
        """Test that the object fields cannot be mutated."""
        result = ExecutionResult(success=True, duration=1.0)
        
        with self.assertRaises(FrozenInstanceError):
            result.success = False # type: ignore
            
        with self.assertRaises(FrozenInstanceError):
            result.duration = 2.0 # type: ignore
            
        with self.assertRaises(FrozenInstanceError):
            result.output = "new output" # type: ignore

    def test_immutability_of_metadata(self):
        """Test that the metadata mapping cannot be mutated."""
        result = ExecutionResult(success=True, duration=1.0, metadata={"initial": "data"})
        
        # MappingProxyType doesn't have a __setitem__ method
        with self.assertRaises(TypeError):
            result.metadata["new_key"] = "new_value" # type: ignore
            
        # The metadata should remain unchanged
        self.assertEqual(result.metadata, {"initial": "data"})

    def test_equality(self):
        """Test that identically constructed ExecutionResult objects are equal."""
        error = ValueError("Same error")
        
        result1 = ExecutionResult(
            success=True, 
            duration=2.5, 
            output="Done", 
            error=error,
            metadata={"source": "test"}
        )
        
        result2 = ExecutionResult(
            success=True, 
            duration=2.5, 
            output="Done", 
            error=error,
            metadata={"source": "test"}
        )
        
        self.assertEqual(result1, result2)
        
        result3 = ExecutionResult(
            success=False, 
            duration=2.5, 
            output="Done", 
            error=error,
            metadata={"source": "test"}
        )
        self.assertNotEqual(result1, result3)


if __name__ == "__main__":
    unittest.main()
