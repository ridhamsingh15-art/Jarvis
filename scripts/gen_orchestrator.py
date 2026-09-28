import os

d = "agents/orchestrator"
os.makedirs(d, exist_ok=True)

files = {}

files["state.py"] = """from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from core.models import JarvisModel

class NodeState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

@dataclass(frozen=True)
class WorkflowNode(JarvisModel):
    id: str
    action: str
    payload: dict[str, Any] = field(default_factory=dict)
    retries: int = 3

@dataclass
class WorkflowState:
    id: str
    nodes: dict[str, WorkflowNode] = field(default_factory=dict)
    dependencies: dict[str, set[str]] = field(default_factory=dict)
    node_states: dict[str, NodeState] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
"""

files["dependency_graph.py"] = """from typing import Any
from .state import WorkflowNode, WorkflowState, NodeState

class CycleError(Exception):
    pass

class DependencyGraph:
    def __init__(self, state: WorkflowState):
        self.state = state

    def add_node(self, node: WorkflowNode, deps: list[str] | None = None) -> None:
        self.state.nodes[node.id] = node
        self.state.dependencies[node.id] = set(deps) if deps else set()
        self.state.node_states[node.id] = NodeState.PENDING

    def get_ready_nodes(self) -> list[WorkflowNode]:
        ready = []
        for nid, deps in self.state.dependencies.items():
            if self.state.node_states[nid] != NodeState.PENDING:
                continue
            # Check if all deps are completed
            if all(self.state.node_states.get(d) == NodeState.COMPLETED for d in deps):
                ready.append(self.state.nodes[nid])
        return ready

    def detect_cycles(self) -> None:
        visited = set()
        path = set()

        def visit(nid: str) -> None:
            if nid in path:
                raise CycleError(f"Cycle detected at node {nid}")
            if nid in visited:
                return
            path.add(nid)
            for d in self.state.dependencies.get(nid, set()):
                visit(d)
            path.remove(nid)
            visited.add(nid)

        for node_id in self.state.nodes:
            visit(node_id)
"""

files["workflow_builder.py"] = """import uuid
from .dependency_graph import DependencyGraph
from .state import WorkflowNode, WorkflowState

class WorkflowBuilder:
    def __init__(self, workflow_id: str):
        self.state = WorkflowState(id=workflow_id)
        self.graph = DependencyGraph(self.state)

    def add_task(self, action: str, deps: list[str] | None = None) -> str:
        nid = f"task_{uuid.uuid4().hex[:8]}"
        self.graph.add_node(WorkflowNode(id=nid, action=action), deps)
        return nid

    def build(self) -> DependencyGraph:
        self.graph.detect_cycles()
        return self.graph
"""

files["planner.py"] = """from .workflow_builder import WorkflowBuilder
from .dependency_graph import DependencyGraph

class OrchestratorPlanner:
    def plan(self, goal: str) -> DependencyGraph:
        builder = WorkflowBuilder(workflow_id="auto_plan")
        # Generate mock workflow for a goal
        n1 = builder.add_task("research")
        n2 = builder.add_task("code", deps=[n1])
        n3 = builder.add_task("test", deps=[n2])
        return builder.build()
"""

files["recovery.py"] = """from .state import WorkflowState, NodeState

class WorkflowRecovery:
    def __init__(self) -> None:
        self._checkpoints: dict[str, dict] = {}

    def checkpoint(self, state: WorkflowState) -> None:
        # Simple mock serialization
        self._checkpoints[state.id] = {
            "states": {k: v.value for k, v in state.node_states.items()},
            "results": state.results.copy()
        }

    def load(self, state: WorkflowState) -> None:
        cp = self._checkpoints.get(state.id)
        if cp:
            for k, v in cp["states"].items():
                state.node_states[k] = NodeState(v)
            state.results.update(cp["results"])
"""

files["executor.py"] = """import asyncio
from .state import WorkflowNode, NodeState, WorkflowState
import random

class WorkflowExecutor:
    async def execute_node(self, node: WorkflowNode, state: WorkflowState) -> None:
        state.node_states[node.id] = NodeState.RUNNING
        
        for attempt in range(node.retries):
            try:
                # Simulate work
                await asyncio.sleep(0.01)
                
                # Mock failure logic based on payload for testing
                if node.payload.get("simulate_fail"):
                    raise RuntimeError("Simulated failure")
                    
                state.results[node.id] = f"Result of {node.action}"
                state.node_states[node.id] = NodeState.COMPLETED
                return
            except Exception as e:
                if attempt == node.retries - 1:
                    state.node_states[node.id] = NodeState.FAILED
                    state.results[node.id] = str(e)
"""

files["coordinator.py"] = """from .state import WorkflowState

class WorkflowCoordinator:
    def merge_outputs(self, state: WorkflowState) -> dict[str, str]:
        return {k: str(v) for k, v in state.results.items()}
"""

files["monitoring.py"] = """from core.events.bus import EventBus
from core.models import Event
from .state import WorkflowState, NodeState

class WorkflowMonitor:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    async def log_status(self, state: WorkflowState) -> None:
        completed = sum(1 for v in state.node_states.values() if v == NodeState.COMPLETED)
        failed = sum(1 for v in state.node_states.values() if v == NodeState.FAILED)
        await self.event_bus.publish_async(Event(
            topic="orchestrator.status.update",
            payload={"workflow": state.id, "completed": completed, "failed": failed}
        ))
"""

files["manager.py"] = """import asyncio
from typing import Any

from core.events.bus import EventBus
from core.models import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .dependency_graph import DependencyGraph, CycleError
from .planner import OrchestratorPlanner
from .executor import WorkflowExecutor
from .scheduler import WorkflowScheduler
from .coordinator import WorkflowCoordinator
from .recovery import WorkflowRecovery
from .monitoring import WorkflowMonitor
from .state import WorkflowState, NodeState

class OrchestratorManager(RuntimeComponent):
    def __init__(self, event_bus: EventBus):
        self._id = Identifier("manager.orchestrator")
        self.event_bus = event_bus
        self.planner = OrchestratorPlanner()
        self.executor = WorkflowExecutor()
        self.coordinator = WorkflowCoordinator()
        self.recovery = WorkflowRecovery()
        self.monitor = WorkflowMonitor(event_bus)
        self.scheduler = WorkflowScheduler(self.executor, self.recovery, self.monitor)
        
        self._is_running = False
        self._active_workflows: dict[str, WorkflowState] = {}

    @property
    def id(self) -> Identifier:
        return self._id

    @property
    def metadata(self) -> ComponentMetadata:
        return ComponentMetadata(id=self._id.value, name="Orchestrator", version="1.0.0")

    @property
    def state(self) -> ComponentState:
        return ComponentState.RUNNING if self._is_running else ComponentState.STOPPED

    async def initialize(self) -> None:
        pass

    async def start(self) -> None:
        self._is_running = True

    async def stop(self) -> None:
        self._is_running = False

    async def health(self) -> HealthReport:
        return HealthReport(
            component_id=self._id.value,
            state=HealthState.HEALTHY if self._is_running else HealthState.UNKNOWN
        )

    async def execute_goal(self, goal: str) -> dict[str, Any]:
        graph = self.planner.plan(goal)
        self._active_workflows[graph.state.id] = graph.state
        await self.scheduler.run_graph(graph)
        return self.coordinator.merge_outputs(graph.state)

    async def resume(self, workflow_id: str) -> dict[str, Any]:
        state = self._active_workflows.get(workflow_id)
        if not state:
            raise ValueError("Unknown workflow")
        self.recovery.load(state)
        # Reset failed nodes to pending
        for k, v in state.node_states.items():
            if v == NodeState.FAILED:
                state.node_states[k] = NodeState.PENDING
                
        graph = DependencyGraph(state)
        await self.scheduler.run_graph(graph)
        return self.coordinator.merge_outputs(state)
"""

files["scheduler.py"] = """import asyncio
from .dependency_graph import DependencyGraph
from .executor import WorkflowExecutor
from .recovery import WorkflowRecovery
from .monitoring import WorkflowMonitor
from .state import NodeState

class WorkflowScheduler:
    def __init__(self, executor: WorkflowExecutor, recovery: WorkflowRecovery, monitor: WorkflowMonitor):
        self.executor = executor
        self.recovery = recovery
        self.monitor = monitor

    async def run_graph(self, graph: DependencyGraph) -> None:
        while True:
            ready = graph.get_ready_nodes()
            
            # Check if done
            if not ready:
                # If any are still running or pending, we are stuck or waiting
                in_progress = any(
                    s in (NodeState.PENDING, NodeState.RUNNING) 
                    for s in graph.state.node_states.values()
                )
                if not in_progress:
                    break
                else:
                    await asyncio.sleep(0.01)
                    continue

            # Execute ready nodes in parallel
            tasks = [self.executor.execute_node(n, graph.state) for n in ready]
            await asyncio.gather(*tasks)
            
            self.recovery.checkpoint(graph.state)
            await self.monitor.log_status(graph.state)
"""

files["__init__.py"] = """from .manager import OrchestratorManager
from .dependency_graph import DependencyGraph, CycleError
from .workflow_builder import WorkflowBuilder
from .state import WorkflowState, WorkflowNode, NodeState

__all__ = [
    "OrchestratorManager",
    "DependencyGraph",
    "CycleError",
    "WorkflowBuilder",
    "WorkflowState",
    "WorkflowNode",
    "NodeState",
]
"""

for fname, fcontent in files.items():
    with open(os.path.join(d, fname), "w") as f:
        f.write(fcontent)
        
tests_file = """import pytest

from core.events.bus import EventBus
from agents.orchestrator import OrchestratorManager, WorkflowBuilder, CycleError
from agents.orchestrator.state import NodeState

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
    results = await orchestrator.resume("test_fail")
    assert builder.graph.state.node_states[n1] == NodeState.COMPLETED
"""

with open("tests/test_orchestrator.py", "w") as f:
    f.write(tests_file)
