import time

import pytest

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
def runtime():
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
    assert events[-1].payload["active_components"] == 0
