import pytest

from core.autonomy import AutonomousGoalManager
from core.bootstrap import Bootstrap, Runtime, StartupResult
from core.models import Event


@pytest.fixture(autouse=True)
def isolated_autonomy_database(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_AUTONOMY_DB", str(tmp_path / "autonomy.sqlite3"))


def test_successful_startup():
    # Make sure we don't have bad env vars breaking config
    # Clean run
    result = Bootstrap.start()
    
    assert isinstance(result, StartupResult)
    assert result.success is True
    assert isinstance(result.runtime, Runtime)
    
    runtime = result.runtime
    assert runtime.container._is_sealed is True
    manager = runtime.container.resolve(AutonomousGoalManager)
    assert isinstance(manager, AutonomousGoalManager)
    # The planner and executor must share one explicit capability registry.
    assert manager._planner._tool_registry is manager._step_executor._tool_registry
    assert {"file", "browser", "windows", "codex_desktop"} <= set(
        manager._planner._tool_registry.list_tools()
    )
    
    # We can subscribe to something to verify EventBus
    events = []
    runtime.event_bus.subscribe("test.*", lambda e: events.append(e.topic))
    runtime.event_bus.publish(Event(topic="test.topic"))
    
    assert events == ["test.topic"]
    
    # Verify Graceful Shutdown
    runtime.shutdown()
    assert runtime.lifecycle.is_stopping is True

def test_startup_failure_recovery(monkeypatch):
    # We can force a failure by mocking ConfigManager.load to raise an exception
    def mock_load(self):
        raise ValueError("Simulated Config Failure")
        
    from core.config import ConfigManager
    monkeypatch.setattr(ConfigManager, "load", mock_load)
    
    result = Bootstrap.start()
    
    assert result.success is False
    assert result.runtime is None
    assert "Simulated Config Failure" in result.error_message

def test_lifecycle_shutdown_events():
    result = Bootstrap.start()
    runtime = result.runtime
    
    events = []
    runtime.event_bus.subscribe("system.stopping", lambda e: events.append(e.topic))
    
    runtime.shutdown()
    
    assert events == ["system.stopping"]
    assert runtime.lifecycle.is_stopping is True
    
    # Calling shutdown again shouldn't break anything
    runtime.shutdown()
