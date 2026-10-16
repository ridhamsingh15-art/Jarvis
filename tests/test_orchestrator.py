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

def test_build_rejects_unknown_dependency():
    builder = WorkflowBuilder("missing_dependency")
    node_id = builder.add_task("consumer")
    builder.graph.state.dependencies[node_id] = {"does_not_exist"}

    with pytest.raises(ValueError, match="unknown dependencies: does_not_exist"):
        builder.build()


def test_build_accepts_dependencies_that_reference_existing_nodes():
    builder = WorkflowBuilder("valid_dependency")
    prerequisite = builder.add_task("prerequisite")
    dependent = builder.add_task("dependent", deps=[prerequisite])

    graph = builder.build()

    assert [node.id for node in graph.get_ready_nodes()] == [prerequisite]
    assert graph.state.dependencies[dependent] == {prerequisite}


@pytest.mark.asyncio
async def test_scheduler_terminates_when_dependency_fails(orchestrator):
    import asyncio

    builder = WorkflowBuilder("failed_dependency")
    prerequisite = builder.add_task("prerequisite")
    dependent = builder.add_task("dependent", deps=[prerequisite])
    builder.graph.state.nodes[prerequisite].payload["simulate_fail"] = True

    await asyncio.wait_for(orchestrator.scheduler.run_graph(builder.build()), timeout=0.5)

    assert builder.graph.state.node_states[prerequisite] == NodeState.FAILED
    assert builder.graph.state.node_states[dependent] == NodeState.FAILED
    assert prerequisite in builder.graph.state.results[dependent]


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
