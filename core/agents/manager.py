import builtins
from typing import Any

from core.events.bus import EventBus
from core.models.domain import Event
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport
from core.telemetry import AsyncLogger

from .collaboration import CollaborationManager
from .dispatcher import TaskDispatcher
from .enums import ConsensusStrategy
from .interfaces import (
    IAgent,
    IAgentRegistry,
    ICoordinator,
    ISharedMemory,
    IVotingMechanism,
)
from .models import AgentResult, AgentTask, SharedContext, Vote


class AgentManager(RuntimeComponent):
    """Orchestrates the Multi-Agent Framework."""

    def __init__(
        self,
        registry: IAgentRegistry,
        coordinator: ICoordinator,
        shared_memory: ISharedMemory,
        voting_engine: IVotingMechanism,
        event_bus: EventBus,
        logger: AsyncLogger
    ) -> None:
        self._registry = registry
        self._coordinator = coordinator
        self._shared_memory = shared_memory
        self._voting = voting_engine
        self._event_bus = event_bus
        self._logger = logger
        
        self._collaboration = CollaborationManager()

        self._state = ComponentState.INITIALIZED
        self._metadata = ComponentMetadata(
            id="core.agents",
            name="Multi-Agent Framework",
            version="1.0.0",
            dependencies=["core.events", "core.telemetry"]
        )

    @property
    def metadata(self) -> ComponentMetadata:
        return self._metadata

    @property
    def state(self) -> ComponentState:
        return self._state

    async def start(self) -> None:
        if self._state in (ComponentState.STARTING, ComponentState.RUNNING):
            return

        self._state = ComponentState.STARTING
        self._logger.info("Starting Multi-Agent System...")
        
        self._state = ComponentState.RUNNING
        self._logger.info("Multi-Agent System started.")

    async def stop(self) -> None:
        if self._state != ComponentState.RUNNING:
            return

        self._state = ComponentState.STOPPING
        self._logger.info("Stopping Multi-Agent System...")
        self._state = ComponentState.STOPPED
        self._logger.info("Multi-Agent System stopped.")

    async def health(self) -> HealthReport:
        try:
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.HEALTHY,
                details={}
            )
        except Exception as e:  # noqa: BLE001
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.UNHEALTHY,
                error=str(e)
            )

    def register(self, agent: IAgent) -> None:
        """Registers a new agent dynamically into the pool."""
        self._registry.register(agent)
        self._publish_event("agent.registered", {"agent_id": agent.profile.id.value, "role": agent.profile.role.value})
        self._logger.info(f"Registered Agent: {agent.profile.id.value}")

    async def assign(self, intent: str, payload: dict[str, Any]) -> AgentResult:
        """Delegates work intelligently through the master coordinator."""
        self._logger.info(f"Assigning task intent: {intent}")
        result = await self._coordinator.assign(intent, payload)
        self._publish_event("agent.finished", {"task_id": result.task_id.value, "status": result.status.value})
        return result

    async def execute_plan(self, plan: Any, parent_mission_id: Any, context: SharedContext) -> builtins.list[AgentResult]:
        """Executes a full sequential plan via the Master Coordinator."""
        self._logger.info(f"Executing multi-agent plan for mission: {parent_mission_id.value}")
        results = await self._coordinator.execute_plan(plan, parent_mission_id, context)
        return results

    async def execute(self, agents: builtins.list[IAgent], tasks: builtins.list[AgentTask], context: SharedContext) -> builtins.list[AgentResult]:
        """Executes jobs manually in parallel across specific agents."""
        for t in tasks:
            self._publish_event("agent.started", {"task_id": t.id.value})
            
        results = await TaskDispatcher.dispatch_parallel(agents, tasks, context)
        
        for r in results:
            self._publish_event("agent.finished", {"task_id": r.task_id.value, "status": r.status.value})
            
        return results

    def broadcast(self, votes: builtins.list[Vote], strategy: ConsensusStrategy) -> Vote | None:
        """Calculates voting outcomes dynamically."""
        result = self._voting.evaluate(votes, strategy)
        if result:
            self._publish_event("agent.vote", {"decision": result.decision.value, "strategy": strategy.value})
        return result
        
    def cancel(self) -> None:
        """Cancels all active tasks globally (stubbed for future cancellation tokens)."""

    def _publish_event(self, topic: str, payload: dict[str, str]) -> None:
        event = Event(
            topic=topic,
            payload=payload,
            source=self.metadata.id
        )
        self._event_bus.publish(event)
