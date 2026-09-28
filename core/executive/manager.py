import logging
from typing import Any, Optional
from core.llm import LLMClient
from core.cognition.context import ShortTermContext
from core.reasoning.execution_plan import ExecutionPlan
from core.reasoning.manager import ReasoningManager
from core.registry import Registry
from core.events.bus import EventBus

from core.models import Identifier
from core.runtime.component import RuntimeComponent
from core.runtime.enums import ComponentState, HealthState
from core.runtime.models import ComponentMetadata, HealthReport
from .decision import ExecutiveDecision, DecisionContext
from .attention import AttentionSystem
from .priorities import PriorityManager
from .policies import ExecutivePolicies
from .interrupt import InterruptHandler
from .arbitration import ConflictArbitrator
from .confidence import ConfidenceEstimator
from .reflection import ReflectionEngine

logger = logging.getLogger(__name__)

class ExecutiveBrain:
    """
    The highest-level decision engine for JARVIS. 
    It reasons before every response to determine the execution strategy.
    """
    
    def __init__(self, llm_client: LLMClient, registry: Registry, event_bus: EventBus = None, agent_manager: Any = None, experience_manager: Any = None, world_manager: Any = None):
        self._reasoning_manager = ReasoningManager(event_bus=event_bus, llm_client=llm_client, registry=registry)
        self._agent_manager = agent_manager
        self._experience_manager = experience_manager
        self._world_manager = world_manager
        
    def plan(self, user_input: str, context: ShortTermContext, topic: Optional[str] = None) -> ExecutionPlan:
        """
        Analyze the user input and determine the execution plan using the deliberation engine.
        If an ExperienceManager is configured and a topic is provided, prior lessons are
        injected into the planning context before deliberation.
        """
        logger.info("ExecutiveBrain delegating to Reasoning Loop...")
        
        # Enrich context with current world state if available
        if self._world_manager:
            try:
                world_block = self._world_manager.snapshot_for_prompt()
                context.inject_system_note(world_block)
                logger.info("Injected World Model snapshot into planning context")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Could not inject World Model: {e}")
        
        # Enrich context with prior experience if available
        if self._experience_manager and topic:
            try:
                retrieval_ctx = self._experience_manager.retrieve_context(topic)
                experience_block = retrieval_ctx.format_for_prompt()
                context.inject_system_note(experience_block)
                logger.info(f"Injected {len(retrieval_ctx.applicable_lessons)} prior lessons for topic='{topic}'")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Could not retrieve experience context: {e}")
        
        # 1. Deliberate to form complete execution plan
        plan = self._reasoning_manager.deliberate(user_input, context)
        
        logger.info("ExecutiveBrain planning complete.")
        
        return plan
        
    async def execute(self, plan: ExecutionPlan, parent_mission_id: Any, context: ShortTermContext) -> Any:
        """
        Coordinates the multi-agent execution of the generated plan.
        """
        if not self._agent_manager:
            logger.warning("AgentManager not configured, cannot execute plan.")
            return []
            
        logger.info(f"ExecutiveBrain delegating execution to AgentManager for mission {parent_mission_id.value}...")
        
        from core.agents.models import SharedContext
        agent_context = SharedContext(
            session_id=parent_mission_id,
            read_only_data=context.get_context_summary()
        )
        
        results = await self._agent_manager.execute_plan(plan, parent_mission_id, agent_context)
        return results


class ExecutiveManager(RuntimeComponent):
    def __init__(self, event_bus: EventBus):
        self._id = Identifier("manager.executive")
        self.event_bus = event_bus
        
        self.attention = AttentionSystem()
        self.priorities = PriorityManager()
        self.policies = ExecutivePolicies()
        self.interrupt_handler = InterruptHandler(event_bus)
        self.arbitrator = ConflictArbitrator()
        self.confidence = ConfidenceEstimator()
        self.reflection = ReflectionEngine()
        
        self._is_running = False

    @property
    def id(self) -> Identifier:
        return self._id

    @property
    def metadata(self) -> ComponentMetadata:
        return ComponentMetadata(id=self._id.value, name="Executive Function", version="1.0.0")

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

    async def evaluate_context(self, context: DecisionContext, recommendations: dict[str, ExecutiveDecision]) -> ExecutiveDecision:
        policy_decision = self.policies.evaluate(context)
        if policy_decision:
            recommendations["policies"] = policy_decision
            
        final_decision = self.arbitrator.resolve(recommendations)
        
        if final_decision in (ExecutiveDecision.PAUSE, ExecutiveDecision.CANCEL, ExecutiveDecision.ESCALATE):
            await self.interrupt_handler.interrupt(f"Triggered by decision {final_decision.value}")
            
        return final_decision

    def record_outcome(self, context: DecisionContext, decision: ExecutiveDecision, outcome: str) -> None:
        self.reflection.reflect(context, decision, outcome)

