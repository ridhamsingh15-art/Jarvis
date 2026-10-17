from dataclasses import FrozenInstanceError

import pytest

from core.models import (
    Command,
    Context,
    ExecutionState,
    Identifier,
    Metadata,
    ModelValidationError,
    Permission,
    Task,
    Version,
)


def test_identifier_validation():
    # Valid
    uid = Identifier()
    assert uid.value is not None
    
    uid2 = Identifier(value="my-custom-id")
    assert uid2.value == "my-custom-id"
    
    # Invalid
    with pytest.raises(ModelValidationError):
        Identifier(value="")
        
    with pytest.raises(ModelValidationError):
        Identifier(value=123)

def test_version_validation():
    v = Version(1, 2, 3, "beta")
    assert str(v) == "1.2.3-beta"
    
    with pytest.raises(ModelValidationError):
        Version(-1, 0, 0)

def test_immutability():
    task = Task(name="Scrape web")
    with pytest.raises(FrozenInstanceError):
        task.name = "New name"

def test_deep_copy():
    v1 = Version(1, 0, 0)
    v2 = v1.copy(minor=1)
    
    assert v1.minor == 0
    assert v2.minor == 1
    assert v1 is not v2

def test_serialization():
    ctx = Context(
        correlation_id=Identifier("c-123"),
        session_id=Identifier("s-123"),
        permissions=[Permission.ADMIN, Permission.USER],
        metadata=Metadata(tags={"env": "prod"})
    )
    cmd = Command(
        id=Identifier("cmd-1"),
        action="fetch",
        parameters={"url": "https://google.com"},
        context=ctx
    )
    
    payload = cmd.to_dict()
    assert payload["id"]["value"] == "cmd-1"
    assert payload["action"] == "fetch"
    assert payload["context"]["permissions"] == [Permission.ADMIN.value, Permission.USER.value]
    assert payload["context"]["metadata"]["tags"]["env"] == "prod"

def test_deserialization():
    payload = {
        "id": {"value": "task-abc"},
        "name": "Process Data",
        "state": ExecutionState.RUNNING.value,
        "version": {"major": 2, "minor": 0, "patch": 1, "label": ""},
        "commands": [
            {
                "id": {"value": "cmd-xyz"},
                "action": "load",
                "parameters": {},
                "context": None
            }
        ],
        "result": None,
        "created_at": {"iso_value": "2023-01-01T00:00:00+00:00"},
        "updated_at": {"iso_value": "2023-01-01T00:00:00+00:00"},
        "metadata": {"tags": {}, "annotations": {}},
        "description": ""
    }
    
    task = Task.from_dict(payload)
    assert isinstance(task, Task)
    assert task.id.value == "task-abc"
    assert task.state == ExecutionState.RUNNING
    assert task.version.major == 2
    assert len(task.commands) == 1
    assert task.commands[0].action == "load"
    assert isinstance(task.commands[0].id, Identifier)

def test_equality_and_hashing():
    v1 = Version(1, 0, 0)
    v2 = Version(1, 0, 0)
    v3 = Version(1, 0, 1)
    
    assert v1 == v2
    assert v1 != v3
    
    # Hashable in sets
    s = {v1, v2, v3}
    assert len(s) == 2
