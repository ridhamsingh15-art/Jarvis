"""
Phase C Tests — Lifecycle Hooks

Tests:
1. pre_tool fires
2. post_tool fires
3. tool_failed fires
4. mission_start fires
5. mission_end fires
6. session_start fires
7. session_end fires
8. hook failure isolation (bad handler doesn't crash primary)
9. no bus → no error (graceful noop)
"""
import pytest
from unittest.mock import MagicMock, call
from core.lifecycle_hooks import LifecycleHooks, LifecycleEvent


def _make_bus_and_hooks():
    """Create a LifecycleHooks with a mock EventBus that captures publishes."""
    bus = MagicMock()
    hooks = LifecycleHooks(event_bus=bus)
    return bus, hooks


class TestLifecycleHooksFire:
    def test_pre_tool_fires(self):
        bus, hooks = _make_bus_and_hooks()
        hooks.pre_tool("windows", "open_app", {"app": "calc"}, request_id="r1")
        bus.publish.assert_called_once()
        event = bus.publish.call_args[0][0]
        assert event.topic == LifecycleEvent.PRE_TOOL.value
        assert event.payload["tool"] == "windows"
        assert event.payload["request_id"] == "r1"

    def test_post_tool_fires(self):
        bus, hooks = _make_bus_and_hooks()
        hooks.post_tool("windows", "open_app", "Calculator opened", 42.0, request_id="r2")
        event = bus.publish.call_args[0][0]
        assert event.topic == LifecycleEvent.POST_TOOL.value
        assert event.payload["action"] == "open_app"
        assert event.payload["latency_ms"] == 42.0

    def test_tool_failed_fires(self):
        bus, hooks = _make_bus_and_hooks()
        hooks.tool_failed("file", "delete_file", "Permission denied", request_id="r3")
        event = bus.publish.call_args[0][0]
        assert event.topic == LifecycleEvent.TOOL_FAILED.value
        assert "Permission denied" in event.payload["error"]

    def test_mission_start_fires(self):
        bus, hooks = _make_bus_and_hooks()
        hooks.mission_start("m-001", "research AI trends")
        event = bus.publish.call_args[0][0]
        assert event.topic == LifecycleEvent.MISSION_START.value
        assert event.payload["mission_id"] == "m-001"

    def test_mission_end_fires(self):
        bus, hooks = _make_bus_and_hooks()
        hooks.mission_end("m-001", succeeded=True, latency_ms=1234.5)
        event = bus.publish.call_args[0][0]
        assert event.topic == LifecycleEvent.MISSION_END.value
        assert event.payload["succeeded"] is True

    def test_session_start_fires(self):
        bus, hooks = _make_bus_and_hooks()
        hooks.session_start("sess-001", "hello jarvis")
        event = bus.publish.call_args[0][0]
        assert event.topic == LifecycleEvent.SESSION_START.value
        assert event.payload["session_id"] == "sess-001"

    def test_session_end_fires(self):
        bus, hooks = _make_bus_and_hooks()
        hooks.session_end("sess-001", task_count=3, latency_ms=500.0)
        event = bus.publish.call_args[0][0]
        assert event.topic == LifecycleEvent.SESSION_END.value
        assert event.payload["task_count"] == 3


class TestLifecycleHooksIsolation:
    def test_hook_failure_does_not_propagate(self):
        """A crashing EventBus handler must not crash the primary request."""
        bus = MagicMock()
        bus.publish.side_effect = RuntimeError("Bus exploded!")
        hooks = LifecycleHooks(event_bus=bus)
        # Must not raise
        hooks.pre_tool("windows", "open_app", {})
        hooks.post_tool("windows", "open_app", "done", 10.0)

    def test_no_bus_noop(self):
        """LifecycleHooks with no EventBus silently does nothing."""
        hooks = LifecycleHooks(event_bus=None)
        hooks.pre_tool("windows", "open_app", {})   # no error
        hooks.mission_start("m-x", "test")           # no error
        hooks.session_end("s-x", 0, 0.0)             # no error


class TestLifecycleHooksTopics:
    def test_all_topics_are_namespaced(self):
        """Every LifecycleEvent topic should start with 'lifecycle.'"""
        for event in LifecycleEvent:
            assert event.value.startswith("lifecycle."), f"Bad topic: {event.value}"

    def test_all_events_covered(self):
        """Ensure LifecycleHooks has a method for each LifecycleEvent."""
        hooks = LifecycleHooks()
        method_names = {
            LifecycleEvent.PRE_TOOL: "pre_tool",
            LifecycleEvent.POST_TOOL: "post_tool",
            LifecycleEvent.TOOL_FAILED: "tool_failed",
            LifecycleEvent.MISSION_START: "mission_start",
            LifecycleEvent.MISSION_END: "mission_end",
            LifecycleEvent.SESSION_START: "session_start",
            LifecycleEvent.SESSION_END: "session_end",
            LifecycleEvent.AGENT_START: "agent_start",
            LifecycleEvent.AGENT_STOP: "agent_stop",
        }
        for event, method in method_names.items():
            assert hasattr(hooks, method), f"Missing method for {event.value}"
