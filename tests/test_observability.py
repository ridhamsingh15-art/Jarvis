import pytest

from core.events.bus import EventBus
from core.observability import ObservabilityManager


class MockLogger:
    def info(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def debug(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    async def log_async(self, *args, **kwargs): pass

@pytest.fixture
def event_bus():
    return EventBus(MockLogger())

@pytest.fixture
def observability(event_bus):
    return ObservabilityManager(event_bus)

@pytest.mark.asyncio
async def test_trace_propagation(observability):
    trace = observability.start_trace()
    with trace.span("root"):
        with trace.span("child1"):
            pass
        with trace.span("child2"):
            pass
    
    assert len(trace.spans) == 3
    assert trace.spans[1].parent_id == trace.spans[0].id
    assert trace.spans[2].parent_id == trace.spans[0].id

@pytest.mark.asyncio
async def test_dashboard_metrics(observability):
    dash = observability.dashboard()
    assert dash["system.cpu.usage"] == 45.0
    assert dash["system.ram.usage"] == 60.0

@pytest.mark.asyncio
async def test_alerts(observability):
    # Set high RAM
    observability.metrics().get_gauge("system.ram.usage").set(95.0)
    
    # We could assert the event bus publish, but for now we just run it
    await observability.alerts.evaluate()
    assert observability.diagnostics.scan() == ["High RAM usage detected."]

@pytest.mark.asyncio
async def test_recording_and_replay(observability):
    trace = observability.start_trace()
    with trace.span("job1"):
        pass
    
    observability.end_trace(trace)
    
    history = observability.replay(trace.trace_id)
    assert len(history) == 1
    assert history[0]["name"] == "job1"
