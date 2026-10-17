import os

d = "core/reasoning"
os.makedirs(d, exist_ok=True)

files = {}

files["enums.py"] = """from enum import StrEnum

class ReasoningType(StrEnum):
    DEDUCTIVE = "DEDUCTIVE"
    INDUCTIVE = "INDUCTIVE"
    ABDUCTIVE = "ABDUCTIVE"
    PROBABILISTIC = "PROBABILISTIC"
    TEMPORAL = "TEMPORAL"
    CAUSAL = "CAUSAL"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    GOAL_ORIENTED = "GOAL_ORIENTED"

class EntityType(StrEnum):
    OBJECT = "OBJECT"
    PERSON = "PERSON"
    GOAL = "GOAL"
    RESOURCE = "RESOURCE"
    ACTION = "ACTION"
"""

files["exceptions.py"] = """class ReasoningError(Exception):
    pass

class SimulationError(Exception):
    pass
"""

files["models.py"] = """from dataclasses import dataclass, field
from core.models import JarvisModel
from .enums import EntityType

@dataclass(frozen=True)
class Entity(JarvisModel):
    id: str
    name: str
    type: EntityType
    properties: dict[str, str] = field(default_factory=dict)

@dataclass(frozen=True)
class Relation(JarvisModel):
    source_id: str
    target_id: str
    relation_type: str
    weight: float = 1.0

@dataclass(frozen=True)
class Inference(JarvisModel):
    conclusion: str
    confidence: float
    evidence: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class Hypothesis(JarvisModel):
    id: str
    description: str
    expected_outcome: str

@dataclass(frozen=True)
class SimulationResult(JarvisModel):
    success_probability: float
    execution_time_ms: float
    resource_cost: dict[str, float]
    is_viable: bool
"""

files["interfaces.py"] = """from abc import ABC, abstractmethod
from typing import Any
from .models import Inference

class IReasoner(ABC):
    @abstractmethod
    def reason(self, context: dict[str, Any]) -> list[Inference]:
        pass
"""

files["knowledge_graph.py"] = """import threading
from .models import Entity, Relation

class KnowledgeGraph:
    def __init__(self) -> None:
        self.entities: dict[str, Entity] = {}
        self.relations: list[Relation] = []
        self._lock = threading.RLock()

    def add_entity(self, entity: Entity) -> None:
        with self._lock:
            self.entities[entity.id] = entity

    def add_relation(self, relation: Relation) -> None:
        with self._lock:
            self.relations.append(relation)

    def get_relations(self, source_id: str) -> list[Relation]:
        with self._lock:
            return [r for r in self.relations if r.source_id == source_id]
"""

files["world_model.py"] = """from .knowledge_graph import KnowledgeGraph

class WorldModel:
    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph

    def get_state(self) -> dict[str, str]:
        # Return a flattened representation of the active world
        with self.graph._lock:
            return {e.name: e.type.value for e in self.graph.entities.values()}
"""

files["causal_reasoner.py"] = """from typing import Any
from .interfaces import IReasoner
from .models import Inference
from .world_model import WorldModel

class CausalReasoner(IReasoner):
    def __init__(self, world: WorldModel):
        self.world = world

    def reason(self, context: dict[str, Any]) -> list[Inference]:
        # Mock causal inference
        if "action" in context:
            return [Inference("Outcome A", 0.8, ["action triggered"])]
        return []
"""

files["logical_reasoner.py"] = """from typing import Any
from .interfaces import IReasoner
from .models import Inference
from .world_model import WorldModel

class LogicalReasoner(IReasoner):
    def __init__(self, world: WorldModel):
        self.world = world

    def reason(self, context: dict[str, Any]) -> list[Inference]:
        # Mock deductive inference
        state = self.world.get_state()
        if "rain" in state and state["rain"] == "OBJECT":
            return [Inference("Ground is wet", 1.0, ["rain exists"])]
        return []
"""

files["probabilistic_reasoner.py"] = """from typing import Any
from .interfaces import IReasoner
from .models import Inference
from .world_model import WorldModel

class ProbabilisticReasoner(IReasoner):
    def __init__(self, world: WorldModel):
        self.world = world

    def reason(self, context: dict[str, Any]) -> list[Inference]:
        # Mock risk assessment
        risk_level = context.get("risk", 0.5)
        return [Inference("Risk Assessment", 1.0 - risk_level, ["historical data"])]
"""

files["hypothesis.py"] = """import uuid
from .models import Hypothesis

class HypothesisGenerator:
    def generate(self, goal: str) -> list[Hypothesis]:
        return [
            Hypothesis(
                id=uuid.uuid4().hex[:8],
                description=f"Plan A to achieve {goal}",
                expected_outcome="Success in 5 steps"
            ),
            Hypothesis(
                id=uuid.uuid4().hex[:8],
                description=f"Plan B to achieve {goal}",
                expected_outcome="Success in 2 steps but higher risk"
            )
        ]
"""

files["simulation.py"] = """from .models import Hypothesis, SimulationResult
from .exceptions import SimulationError

class ExecutionSimulator:
    def simulate(self, hypothesis: Hypothesis) -> SimulationResult:
        # Reject impossible plans based on descriptions
        if "impossible" in hypothesis.description.lower():
            return SimulationResult(
                success_probability=0.0,
                execution_time_ms=0.0,
                resource_cost={},
                is_viable=False
            )
            
        return SimulationResult(
            success_probability=0.85,
            execution_time_ms=120.0,
            resource_cost={"cpu": 10.0},
            is_viable=True
        )
"""

files["planner_bridge.py"] = """from typing import Any
from .models import SimulationResult, Hypothesis

class PlannerBridge:
    def format_plan(self, hypothesis: Hypothesis, result: SimulationResult) -> dict[str, Any]:
        return {
            "plan_id": hypothesis.id,
            "description": hypothesis.description,
            "success_prob": result.success_probability,
            "viable": result.is_viable
        }
"""

files["manager.py"] = """import asyncio
from typing import Any

from core.events.bus import EventBus
from core.models import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .knowledge_graph import KnowledgeGraph
from .world_model import WorldModel
from .logical_reasoner import LogicalReasoner
from .causal_reasoner import CausalReasoner
from .probabilistic_reasoner import ProbabilisticReasoner
from .hypothesis import HypothesisGenerator
from .simulation import ExecutionSimulator
from .planner_bridge import PlannerBridge
from .models import Inference, Hypothesis, SimulationResult

class ReasoningManager(RuntimeComponent):
    def __init__(self, event_bus: EventBus):
        self._id = Identifier("manager.reasoning")
        self.event_bus = event_bus
        
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
"""

files["__init__.py"] = """from .manager import ReasoningManager
from .models import Hypothesis, SimulationResult, Entity, Relation, Inference
from .enums import ReasoningType, EntityType

__all__ = [
    "ReasoningManager",
    "Hypothesis",
    "SimulationResult",
    "Entity",
    "Relation",
    "Inference",
    "ReasoningType",
    "EntityType"
]
"""

for fname, fcontent in files.items():
    with open(os.path.join(d, fname), "w") as f:
        f.write(fcontent)

tests_file = """import pytest

from core.events.bus import EventBus
from core.reasoning import ReasoningManager, Entity, EntityType, Hypothesis

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
def reasoning(event_bus):
    return ReasoningManager(event_bus)

@pytest.mark.asyncio
async def test_deductive_reasoning(reasoning):
    # Setup world model
    reasoning.graph.add_entity(Entity(id="1", name="rain", type=EntityType.OBJECT))
    
    inferences = await reasoning.reason({"context": "test"})
    assert any(i.conclusion == "Ground is wet" for i in inferences)

@pytest.mark.asyncio
async def test_probabilistic_reasoning(reasoning):
    inferences = await reasoning.reason({"risk": 0.2})
    prob_inf = next(i for i in inferences if i.conclusion == "Risk Assessment")
    assert prob_inf.confidence == 0.8

@pytest.mark.asyncio
async def test_simulation_rejection(reasoning):
    hyp = Hypothesis(id="imp", description="This is an impossible plan", expected_outcome="fail")
    res = await reasoning.simulate(hyp)
    assert not res.is_viable
    assert res.success_probability == 0.0

@pytest.mark.asyncio
async def test_evaluate_goal(reasoning):
    best_plan = await reasoning.evaluate("Build a web app")
    assert best_plan is not None
    assert best_plan["viable"] is True
    assert best_plan["success_prob"] == 0.85

@pytest.mark.asyncio
async def test_thread_safety(reasoning):
    import asyncio
    
    def add_concurrent():
        reasoning.graph.add_entity(Entity(id="x", name="x", type=EntityType.OBJECT))
        
    await asyncio.gather(
        asyncio.to_thread(add_concurrent),
        asyncio.to_thread(add_concurrent)
    )
    assert "x" in reasoning.graph.entities
"""

with open("tests/test_reasoning.py", "w") as f:
    f.write(tests_file)
