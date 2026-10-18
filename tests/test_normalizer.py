import pytest

from core.normalizer import normalize
from core.registry import Registry
from core.task import Task
from core.validator import Validator
from tools.file import FileTool


@pytest.fixture
def validator():
    registry = Registry()
    registry.register(FileTool())
    return Validator(registry)


@pytest.mark.parametrize("action", ["patch_file", "edit_file"])
def test_target_alias_remains_patch_search_text_for_file_edit_actions(action, validator):
    normalized = normalize({
        "tool": "file",
        "action": action,
        "args": {
            "path": "example.txt",
            "target": "old content",
            "replacement": "new content",
        },
    })

    assert normalized[0]["args"] == {
        "path": "example.txt",
        "target": "old content",
        "replacement": "new content",
    }
    validator.validate(Task(
        tool=normalized[0]["tool"],
        action=normalized[0]["action"],
        args=normalized[0]["args"],
    ))


@pytest.mark.parametrize("action", ["move", "copy"])
def test_target_alias_still_maps_to_destination_for_file_transfer_actions(action, validator):
    normalized = normalize({
        "tool": "filesystem",
        "action": action,
        "args": {"source": "from.txt", "target": "to.txt"},
    })

    assert normalized[0]["tool"] == "file"
    assert normalized[0]["args"] == {"path": "from.txt", "dest": "to.txt"}
    validator.validate(Task(
        tool=normalized[0]["tool"],
        action=normalized[0]["action"],
        args=normalized[0]["args"],
    ))
