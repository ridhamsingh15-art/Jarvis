import pytest

from core.executor import ExecutorManager
from core.executor.isolated_handler import IsolatedToolHandler


def _manager():
    # Registration-contract tests do not start workers or execute tasks.
    return ExecutorManager(event_bus=object(), task_manager=object(), min_workers=1, max_workers=1)

def _callback(_context=None, **kwargs):
    return {"ok": True}

class _PickleableTool:
    def execute(self, action, args):
        return {"ok": True}

def test_legacy_two_argument_registration_remains_compatible_and_is_audited():
    manager = _manager()
    manager.register_action("legacy.read", _callback)

    audit = manager.registration_audit()
    assert audit["registered_actions"] == ["legacy.read"]
    assert audit["contracts"] == {"legacy.read": "legacy-uncontained"}
    assert audit["uncontained_actions"] == ["legacy.read"]
    assert audit["release_safe"] is False

def test_side_effecting_raw_callback_fails_closed():
    manager = _manager()
    with pytest.raises(TypeError, match="require IsolatedToolHandler"):
        manager.register_action("file.delete", _callback, side_effecting=True)
    assert manager.registration_audit()["registered_actions"] == []

def test_isolated_side_effecting_registration_passes_contract_gate():
    manager = _manager()
    handler = IsolatedToolHandler(tool=_PickleableTool(), action="delete")
    manager.register_action("file.delete", handler, side_effecting=True)

    audit = manager.registration_audit()
    assert audit["contracts"] == {"file.delete": "isolated-side-effect"}
    assert audit["uncontained_actions"] == []
    assert audit["release_safe"] is True

def test_registration_rejects_invalid_names_and_non_callable_handlers():
    manager = _manager()
    with pytest.raises(ValueError, match="non-empty string"):
        manager.register_action("  ", _callback)
    with pytest.raises(TypeError, match="must be callable"):
        manager.register_action("bad", object())
    with pytest.raises(TypeError, match="must be a bool"):
        manager.register_action("bad.flag", _callback, side_effecting="yes")


def test_side_effecting_registration_rejects_invalid_isolated_descriptor():
    manager = _manager()
    handler = IsolatedToolHandler(tool=object(), action="delete")
    with pytest.raises(Exception, match="must expose callable execute"):
        manager.register_action("file.delete", handler, side_effecting=True)
    assert manager.registration_audit()["registered_actions"] == []


def test_registration_audit_detects_direct_registry_bypass_and_replacement():
    manager = _manager()
    isolated = IsolatedToolHandler(tool=_PickleableTool(), action="delete")
    manager.register_action("file.delete", isolated, side_effecting=True)
    assert manager.registration_audit()["release_safe"] is True

    # The registry remains public for compatibility; direct writes must not evade the gate.
    manager.registry.register("shell.run", _callback)
    audit = manager.registration_audit()
    assert audit["uncontained_actions"] == ["shell.run"]
    assert audit["release_safe"] is False

    manager.registry.register("file.delete", _callback)
    audit = manager.registration_audit()
    assert set(audit["uncontained_actions"]) == {"file.delete", "shell.run"}
    assert audit["release_safe"] is False
