
from core.events.bus import EventBus
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .arbitration import ConflictArbitrator
from .attention import AttentionSystem
from .confidence import ConfidenceEstimator
from .decision import DecisionContext, ExecutiveDecision
from .interrupt import InterruptHandler
from .policies import ExecutivePolicies
from .priorities import PriorityManager
from .reflection import ReflectionEngine


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
