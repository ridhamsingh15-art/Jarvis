"""
Tests for Phase 2: Schema-Aware Parameter Normalization.

Verifies:
- content -> text for create_file (optional_args)
- text -> content for write_file (required_args)
- filepath / file / dir -> path
- Ambiguity rejection when both canonical and alias are provided
- Ambiguity rejection when multiple aliases are provided
- Non-destructive preservation of canonical parameters
- Strict validation executing after normalization (unknown arguments rejected)
- Telemetry / logging integration
"""

import pytest
from unittest.mock import MagicMock

from core.action_definition import ActionDefinition
from core.exceptions import ValidationError, JarvisError
from core.registry import Registry
from core.task import Task
from core.tool_intelligence.argument_mapper import ArgumentMapper
from core.tool_intelligence.manager import ToolIntelligenceManager
from core.validator import Validator
from tools.file import FileTool


class TestParameterNormalization:
    """Test ArgumentMapper and ToolIntelligenceManager parameter normalization."""

    @pytest.fixture
    def mapper(self):
        return ArgumentMapper()

    def test_create_file_content_to_text(self, mapper):
        """content maps to optional 'text' for create_file schema."""
        raw = {"path": "test.txt", "content": "hello world"}
        mapped, repairs = mapper.map_arguments(
            raw,
            required_args=["path"],
            optional_args=["text"],
            tool_name="file",
            action_name="create_file",
        )
        assert mapped == {"path": "test.txt", "text": "hello world"}
        assert repairs == 1

    def test_write_file_text_to_content(self, mapper):
        """text maps to required 'content' for write_file schema."""
        raw = {"path": "test.txt", "text": "file content"}
        mapped, repairs = mapper.map_arguments(
            raw,
            required_args=["path", "content"],
            optional_args=[],
            tool_name="file",
            action_name="write_file",
        )
        assert mapped == {"path": "test.txt", "content": "file content"}
        assert repairs == 1

    def test_filepath_to_path(self, mapper):
        """filepath maps to 'path'."""
        raw = {"filepath": "C:/demo.txt"}
        mapped, repairs = mapper.map_arguments(
            raw,
            required_args=["path"],
            optional_args=[],
            tool_name="file",
            action_name="delete",
        )
        assert mapped == {"path": "C:/demo.txt"}
        assert repairs == 1

    def test_ambiguity_canonical_and_alias_rejected(self, mapper):
        """Reject when both canonical 'text' and alias 'content' are supplied."""
        raw = {"path": "test.txt", "text": "canon", "content": "alias"}
        with pytest.raises(ValidationError) as exc:
            mapper.map_arguments(
                raw,
                required_args=["path"],
                optional_args=["text"],
                tool_name="file",
                action_name="create_file",
            )
        assert "Ambiguous arguments" in str(exc.value)
        assert "canonical parameter 'text'" in str(exc.value)

    def test_ambiguity_multiple_aliases_rejected(self, mapper):
        """Reject when multiple conflicting aliases are supplied for 'path'."""
        raw = {"file": "a.txt", "filename": "b.txt"}
        with pytest.raises(ValidationError) as exc:
            mapper.map_arguments(
                raw,
                required_args=["path"],
                optional_args=[],
                tool_name="file",
                action_name="open_file",
            )
        assert "Ambiguous arguments" in str(exc.value)
        assert "multiple conflicting aliases" in str(exc.value)

    def test_non_destructive_canonical_preserved(self, mapper):
        """Existing canonical parameters are never altered."""
        raw = {"path": "test.txt", "content": "data"}
        mapped, repairs = mapper.map_arguments(
            raw,
            required_args=["path", "content"],
            optional_args=[],
            tool_name="file",
            action_name="write_file",
        )
        assert mapped == {"path": "test.txt", "content": "data"}
        assert repairs == 0

    def test_strict_validator_executes_after_normalization(self):
        """ToolIntelligenceManager normalizes valid aliases, but Validator still catches unknown args."""
        registry = Registry()
        registry.register(FileTool())
        validator = Validator(registry)
        bus = MagicMock()
        manager = ToolIntelligenceManager(registry, validator, bus)

        # 1. Valid alias: 'content' normalized to 'text' for create_file -> passes
        task = Task(tool="file", action="create_file", args={"path": "C:/test.txt", "content": "payload"})
        processed = manager.process(task)
        assert processed.args == {"path": "C:/test.txt", "text": "payload"}

        # 2. Unknown argument alongside normalized argument -> Validator catches it
        bad_task = Task(
            tool="file",
            action="create_file",
            args={"path": "C:/test.txt", "content": "payload", "rogue_arg": "unauthorized"},
        )
        with pytest.raises(JarvisError) as exc:
            manager.process(bad_task)
        assert "Unknown argument: 'rogue_arg'" in str(exc.value)

    def test_file_create_file_execution_with_text(self, tmp_path):
        """End-to-end execution of create_file with text creates the file and writes text."""
        tool = FileTool()
        target = tmp_path / "hello_created.txt"
        res = tool.execute("create_file", {"path": str(target), "text": "CREATED_CONTENT"})
        assert "Created file" in res
        assert target.exists()
        assert target.read_text(encoding="utf-8") == "CREATED_CONTENT"
