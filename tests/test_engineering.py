import pytest

from core.events.bus import EventBus
from engineering.manager import EngineeringManager
from engineering.project import ProjectPhase


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
def engineering(event_bus):
    return EngineeringManager(event_bus)

@pytest.mark.asyncio
async def test_requirement_parsing(engineering):
    from engineering.project import ProjectState
    state = ProjectState(id="1", objective="Web App")
    stories = engineering.backlog.parse(state)
    assert len(stories) == 2

@pytest.mark.asyncio
async def test_repair_loop(engineering):
    from engineering.project import ProjectState
    state = ProjectState(id="2", objective="fail_test_app")
    
    # Should fix it internally
    success = engineering.testing.repair_loop(state)
    assert success is True
    assert state.objective == "fixed_test_app"

@pytest.mark.asyncio
async def test_documentation(engineering):
    from engineering.project import ProjectState
    state = ProjectState(id="3", objective="App")
    docs = engineering.documentation.generate(state)
    assert "README.md" in docs

@pytest.mark.asyncio
async def test_pipeline(engineering):
    # Test entire pipeline runs to end
    state = await engineering.execute_project("p1", "Simple App")
    assert state.phase == ProjectPhase.DEPLOYMENT
    assert len(state.errors) == 0

@pytest.mark.asyncio
async def test_pipeline_failure_recovery(engineering):
    # If the repair loop completely fails (we inject a failure that can't be fixed)
    # Actually wait, repair loop fixes "fail_test", so to make it completely fail:
    # the repair loop in our mock specifically replaces "fail_test" with "fixed_test".
    # if it doesn't have "fail_test" but still fails, let's mock the run_tests on harness.
    
    # We will just patch harness
    engineering.testing.run_tests = lambda s: {"success": False, "error": "fatal"}
    
    state = await engineering.execute_project("p2", "Fatal App")
    # It will fail, recovery controller drops it to IMPLEMENTATION
    assert state.phase == ProjectPhase.IMPLEMENTATION
    assert len(state.errors) == 0 # Recovery clears errors
