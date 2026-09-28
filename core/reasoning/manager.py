from typing import Any

from core.events.bus import EventBus
from core.models import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .causal_reasoner import CausalReasoner
from .hypothesis import HypothesisGenerator
from .knowledge_graph import KnowledgeGraph
from .logical_reasoner import LogicalReasoner
from .models import Hypothesis, Inference, SimulationResult
from .planner_bridge import PlannerBridge
from .probabilistic_reasoner import ProbabilisticReasoner
from .simulation import ExecutionSimulator
from .world_model import WorldModel
from core.llm import LLMClient
from core.registry import Registry
from core.cognition.context import ShortTermContext
from core.reasoning.execution_plan import ExecutionPlan
from core.reasoning.loop import ReasoningLoop

class ReasoningManager(RuntimeComponent):
    def __init__(self, event_bus: EventBus, llm_client: LLMClient = None, registry: Registry = None):
        self._id = Identifier("manager.reasoning")
        self.event_bus = event_bus
        self._llm = llm_client
        self._registry = registry
        
        # New deliberation engine
        if self._llm and self._registry:
            self._loop = ReasoningLoop(self._llm, self._registry)
        else:
            self._loop = None
        
        self.graph = KnowledgeGraph()
        self.world = WorldModel(self.graph)
        
        self.logical = LogicalReasoner(self.world)
        self.causal = CausalReasoner(self.world)
        self.probabilistic = ProbabilisticReasoner(self.world)
        
        self.generator = HypothesisGenerator()
        self.simulator = ExecutionSimulator()
        self.bridge = PlannerBridge()
        
        self._is_running = False

    @property
    def id(self) -> Identifier:
        return self._id

    @property
    def metadata(self) -> ComponentMetadata:
        return ComponentMetadata(id=self._id.value, name="Reasoning Engine", version="1.0.0")

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

    async def reason(self, context: dict[str, Any]) -> list[Inference]:
        await self.event_bus.publish_async(Event(topic="reasoning.started", payload={}))
        inferences = []
        inferences.extend(self.logical.reason(context))
        inferences.extend(self.causal.reason(context))
        inferences.extend(self.probabilistic.reason(context))
        await self.event_bus.publish_async(Event(topic="reasoning.completed", payload={"count": len(inferences)}))
        return inferences

    async def simulate(self, hypothesis: Hypothesis) -> SimulationResult:
        result = self.simulator.simulate(hypothesis)
        await self.event_bus.publish_async(Event(topic="reasoning.simulation.finished", payload={"viable": result.is_viable}))
        return result

    async def evaluate(self, goal: str) -> dict[str, Any] | None:
        # Full flow: Generate hypothesis -> Simulate -> Pick best -> Bridge to planner
        hypotheses = self.generator.generate(goal)
        await self.event_bus.publish_async(Event(topic="reasoning.hypothesis.created", payload={"count": len(hypotheses)}))
        
        best_plan = None
        best_prob = -1.0
        
        for hyp in hypotheses:
            res = await self.simulate(hyp)
            if res.is_viable and res.success_probability > best_prob:
                best_prob = res.success_probability
                best_plan = self.bridge.format_plan(hyp, res)
                
        return best_plan

    async def infer(self, context: dict[str, Any]) -> list[Inference]:
        return await self.reason(context)

    async def predict(self, hypothesis: Hypothesis) -> SimulationResult:
        return await self.simulate(hypothesis)

    def explain(self, inference: Inference) -> str:
        return f"Concluded {inference.conclusion} based on {inference.evidence}"

    def deliberate(self, user_input: str, context: ShortTermContext) -> ExecutionPlan:
        """
        Executes the reasoning loop to formulate a comprehensive ExecutionPlan.
        """
        if not self._loop:
            raise RuntimeError("ReasoningManager was not initialized with LLM and Registry for deliberation.")
        return self._loop.run(user_input, context)
