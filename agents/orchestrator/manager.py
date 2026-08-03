from typing import Any

from core.events.bus import EventBus
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .coordinator import WorkflowCoordinator
from .dependency_graph import DependencyGraph
from .executor import WorkflowExecutor
from .monitoring import WorkflowMonitor
from .planner import OrchestratorPlanner
from .recovery import WorkflowRecovery
from .scheduler import WorkflowScheduler
from .state import NodeState, WorkflowState


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
