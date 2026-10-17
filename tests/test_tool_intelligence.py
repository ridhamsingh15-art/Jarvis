"""
Tests for the Tool Intelligence subsystem.
"""

from unittest.mock import MagicMock

from core.action_definition import ActionDefinition
from core.task import Task
from core.tool_intelligence.argument_mapper import ArgumentMapper
from core.tool_intelligence.repair import PayloadRepairer
from core.tool_intelligence.resolver import ToolResolver
from core.tool_intelligence.schema_resolver import SchemaResolver


def test_tool_resolver_alias():
    resolver = ToolResolver()
    
    # Direct alias
    t, a, repaired = resolver.resolve("open_browser", "some_action")
    assert t == "browser"
    assert a == "open_url"
    assert repaired is True
    
    # Action alias within tool
    t, a, repaired = resolver.resolve("file", "create")
    assert t == "file"
    assert a == "write_file"
    assert repaired is True
    
    # No alias
    t, a, repaired = resolver.resolve("browser", "search_google")
    assert t == "browser"
    assert a == "search_google"
    assert repaired is False


def test_argument_mapper_exact():
    mapper = ArgumentMapper()
    mapped, repairs = mapper.map_arguments({"path": "test.txt"}, ["path"])
    assert mapped == {"path": "test.txt"}
    assert repairs == 0


def test_argument_mapper_semantic_repair():
    mapper = ArgumentMapper()
    # Hallucinated "file" instead of "path"
    mapped, repairs = mapper.map_arguments({"file": "test.txt"}, ["path"])
    assert mapped == {"path": "test.txt"}
    assert repairs == 1


def test_argument_mapper_single_fallback_repair():
    mapper = ArgumentMapper()
    # Unknown key but perfectly matches the 1-to-1 fallback
    mapped, repairs = mapper.map_arguments({"unknown_key": "test.txt"}, ["path"])
    assert mapped == {"path": "test.txt"}
    assert repairs == 1


def test_payload_repairer_full_pipeline():
    registry_mock = MagicMock()
    registry_mock.has_tool.return_value = True
    registry_mock.get_actions.return_value = {
        "write_file": ActionDefinition(name="write_file", description="", required_args=["path"])
    }
    
    repairer = PayloadRepairer(
        ToolResolver(),
        SchemaResolver(registry_mock),
        ArgumentMapper()
    )
    
    # LLM hallucinates: tool="create_file", args={"file": "test.txt"}
    bad_task = Task(tool="create_file", action="create_file", args={"file": "test.txt"})
    
    repaired, metrics = repairer.repair(bad_task)
    
    assert repaired.tool == "file"
    assert repaired.action == "write_file"
    assert repaired.args == {"path": "test.txt"}
    
    assert metrics.tool_name_repaired is True
    assert metrics.action_name_repaired is True
    assert metrics.arguments_repaired == 1
    assert metrics.total_arguments == 1
    assert metrics.was_repaired is True


def test_payload_repairer_unresolvable_schema():
    registry_mock = MagicMock()
    registry_mock.has_tool.return_value = False
    
    repairer = PayloadRepairer(
        ToolResolver(),
        SchemaResolver(registry_mock),
        ArgumentMapper()
    )
    
    bad_task = Task(tool="unknown_tool", action="unknown_action", args={})
    
    repaired, metrics = repairer.repair(bad_task)
    
    # Should safely fallback to original, setting repair flags where applicable (none here)
    assert repaired.tool == "unknown_tool"
    assert repaired.action == "unknown_action"
    assert metrics.arguments_repaired == 0
