import pytest

from agents.orchestrator import CycleError, OrchestratorManager, WorkflowBuilder
from agents.orchestrator.state import NodeState
from core.events.bus import EventBus


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
def orchestrator(event_bus):
    return OrchestratorManager(event_bus)

@pytest.mark.asyncio
async def test_execute_goal(orchestrator):
    results = await orchestrator.execute_goal("Deploy app")
    assert len(results) == 3 # mock planner creates 3 tasks
    assert "Result of research" in results.values()

@pytest.mark.asyncio
async def test_cycle_detection():
    builder = WorkflowBuilder("test")
    n1 = builder.add_task("t1")
    n2 = builder.add_task("t2", deps=[n1])
    # manually inject cycle
    builder.graph.state.dependencies[n1] = {n2}
    
    with pytest.raises(CycleError):
        builder.build()

@pytest.mark.asyncio
async def test_failure_and_recovery(orchestrator):
    builder = WorkflowBuilder("test_fail")
    n1 = builder.add_task("fail_task")
    builder.graph.state.nodes[n1].payload["simulate_fail"] = True
    
    orchestrator._active_workflows["test_fail"] = builder.graph.state
    await orchestrator.scheduler.run_graph(builder.graph)
    
    # Should be FAILED
    assert builder.graph.state.node_states[n1] == NodeState.FAILED
    
    # Fix the payload
    builder.graph.state.nodes[n1].payload["simulate_fail"] = False
    
    # Resume
    await orchestrator.resume("test_fail")
    assert builder.graph.state.node_states[n1] == NodeState.COMPLETED
