import time

import pytest

from core.autonomy import AutonomousGoalManager, GoalState
from core.bootstrap import Bootstrap
from core.runtime import (
    BaseComponent,
    ComponentMetadata,
    ComponentNotFoundError,
    ComponentRegistrationError,
    HealthReport,
    HealthState,
    RuntimeKernel,
    RuntimeState,
)


class MockComponent(BaseComponent):
    def __init__(self, name: str, fail_health: bool = False):
        super().__init__(ComponentMetadata(id=name, name=name, version="1.0.0"))
        self.fail_health = fail_health
        
    async def _do_start(self) -> None:
        pass
        
    async def _do_stop(self) -> None:
        pass
        
    async def health(self) -> HealthReport:
        if self.fail_health:
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.DEGRADED,
                details={"reason": "Simulated failure"}
            )
        return await super().health()

@pytest.fixture
def runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_AUTONOMY_DB", str(tmp_path / "autonomy.sqlite3"))
    monkeypatch.setenv("JARVIS_MISSION_DB", str(tmp_path / "crash-missions.sqlite3"))
    monkeypatch.setenv("JARVIS_LLM_PLANNING", "false")
    result = Bootstrap.start()
    yield result.runtime
    # Cleanup after test if still running
    if result.runtime and not result.runtime.lifecycle.is_stopping:
        result.runtime.shutdown()

def test_kernel_state_transitions(runtime):
    kernel = RuntimeKernel(runtime)
    
    assert kernel.state() == RuntimeState.STOPPED
    
    kernel.start()
    assert kernel.state() == RuntimeState.RUNNING
    
    kernel.pause()
    assert kernel.state() == RuntimeState.PAUSED
    
    kernel.resume()
    assert kernel.state() == RuntimeState.RUNNING
    
    kernel.stop()
    assert kernel.state() == RuntimeState.STOPPED

def test_component_registration_and_resolution(runtime):
    kernel = RuntimeKernel(runtime)
    comp = MockComponent("MemorySys")
    
    kernel.register_component(comp)
    
    resolved = kernel._registry.get("MemorySys")
    assert resolved is comp
    
    with pytest.raises(ComponentRegistrationError):
        kernel.register_component(comp)
        
    with pytest.raises(ComponentNotFoundError):
        kernel._registry.get("Missing")

def test_health_aggregation(runtime):
    kernel = RuntimeKernel(runtime)
    
    c1 = MockComponent("ServiceA")
    c2 = MockComponent("ServiceB", fail_health=True)
    
    kernel.register_component(c1)
    kernel.register_component(c2)
    kernel.start()
    
    report = kernel.health_report()
    assert report.state == HealthState.DEGRADED
    
    # Details should contain sub-reports
    assert "components" in report.details
    assert report.details["components"]["ServiceA"]["state"] == HealthState.HEALTHY
    assert report.details["components"]["ServiceB"]["state"] == HealthState.DEGRADED
    
    kernel.stop()

def test_heartbeat_service(runtime):
    kernel = RuntimeKernel(runtime)
    
    # Monkeypatch the interval to run extremely fast for test
    kernel._heartbeat._interval = 0.05
    
    events = []
    runtime.event_bus.subscribe("runtime.heartbeat", lambda e: events.append(e))
    
    kernel.start()
    time.sleep(0.15) # Should fire at least 2 heartbeats
    kernel.stop()
    
    assert len(events) >= 2
    
    # The first event might have been fired while STARTING, so we check the last one
    assert events[-1].payload["state"] == RuntimeState.RUNNING
    assert events[-1].payload["active_components"] == 1


def test_runtime_caller_can_start_persistent_goal(runtime):
    kernel = RuntimeKernel(runtime)
    kernel.start()
    try:
        manager = runtime.container.resolve(AutonomousGoalManager)
        goal = manager.create_goal("Run from the application caller thread")

        # The manager's asyncio loop belongs to RuntimeKernel's worker thread;
        # this synchronous test thread must still be able to submit goal work.
        manager.start_goal(goal.id)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            state = manager.status(goal.id)
            if state in (GoalState.COMPLETED, GoalState.FAILED, GoalState.PAUSED):
                break
            time.sleep(0.01)

        assert manager.status(goal.id) is GoalState.FAILED
        failed_goal = next(item for item in manager.list_goals() if item.id == goal.id)
        assert "couldn't safely map this objective" in failed_goal.metadata["failure_reason"]
    finally:
        kernel.stop()



def test_runtime_executes_real_supported_goal(runtime, tmp_path):
    import json

    from core.autonomy import AutonomousGoalManager

    workspace = tmp_path / "real-goal-files"
    workspace.mkdir()
    for index in range(3):
        (workspace / f"real-file-{index}.txt").write_text(
            f"JARVIS_REAL_EXECUTION_MARKER_{index}\n" + ("sample " * (index + 2)),
            encoding="utf-8",
        )

    kernel = RuntimeKernel(runtime)
    kernel.start()
    try:
        manager = runtime.container.resolve(AutonomousGoalManager)
        goal = manager.create_goal(f"List the 10 largest files in {workspace}")
        manager.start_goal(goal.id)

        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            state = manager.status(goal.id)
            if state in (GoalState.COMPLETED, GoalState.FAILED):
                break
            time.sleep(0.02)

        assert manager.status(goal.id) is GoalState.COMPLETED
        completed_goal = next(item for item in manager.list_goals() if item.id == goal.id)
        results = completed_goal.metadata.get("execution_results", [])
        assert len(results) == 1
        assert results[0]["state"] == "COMPLETED"
        assert results[0]["action"] == "list_largest_files"
        assert "real-file-2.txt" in json.dumps(results, ensure_ascii=False)
    finally:
        kernel.stop()




def test_runtime_goal_respects_destructive_execution_policy(runtime, tmp_path):
    from core.autonomy import AutonomousGoalManager

    target = tmp_path / "must-not-delete.txt"
    target.write_text("preserve this file", encoding="utf-8")
    kernel = RuntimeKernel(runtime)
    kernel.start()
    try:
        manager = runtime.container.resolve(AutonomousGoalManager)
        goal = manager.create_goal(f"delete {target}")
        manager.start_goal(goal.id)

        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            state = manager.status(goal.id)
            if state in (GoalState.COMPLETED, GoalState.FAILED, GoalState.PAUSED):
                break
            time.sleep(0.02)

        assert manager.status(goal.id) is GoalState.PAUSED
        assert target.read_text(encoding="utf-8") == "preserve this file"
        paused_goal = next(item for item in manager.list_goals() if item.id == goal.id)
        assert paused_goal.metadata["intervention_kind"] == "approval_required"
        assert "requires confirmation" in paused_goal.metadata["intervention_required"]
    finally:
        kernel.stop()
