import os

d = "core/executive"
os.makedirs(d, exist_ok=True)

files = {}

files["decision.py"] = """from enum import StrEnum
from dataclasses import dataclass, field
from core.models import JarvisModel

class ExecutiveDecision(StrEnum):
    PROCEED = "PROCEED"
    CLARIFY = "CLARIFY"
    DEFER = "DEFER"
    DELEGATE = "DELEGATE"
    CANCEL = "CANCEL"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    ESCALATE = "ESCALATE"

@dataclass(frozen=True)
class DecisionContext(JarvisModel):
    goal_id: str
    confidence: float
    risk: float
    urgency: float
    sources: list[str] = field(default_factory=list)
"""

files["attention.py"] = """from dataclasses import dataclass

@dataclass
class AttentionState:
    focus: str
    importance: float
    urgency: float
    novelty: float
    risk: float
    confidence: float

class AttentionSystem:
    def __init__(self) -> None:
        self.state = AttentionState(
            focus="idle",
            importance=0.0,
            urgency=0.0,
            novelty=0.0,
            risk=0.0,
            confidence=1.0
        )

    def update(self, **kwargs: float | str) -> None:
        for k, v in kwargs.items():
            if hasattr(self.state, k):
                setattr(self.state, k, v)
"""

files["priorities.py"] = """import queue
from dataclasses import dataclass, field
from typing import Any

@dataclass(order=True)
class PriorityTask:
    priority: int
    task_id: str = field(compare=False)
    payload: dict[str, Any] = field(default_factory=dict, compare=False)

class PriorityManager:
    def __init__(self) -> None:
        self.q: queue.PriorityQueue = queue.PriorityQueue()

    def add_task(self, task_id: str, priority: int, payload: dict[str, Any] | None = None) -> None:
        self.q.put(PriorityTask(priority=priority, task_id=task_id, payload=payload or {}))

    def get_next(self) -> PriorityTask | None:
        if not self.q.empty():
            return self.q.get()
        return None
"""

files["policies.py"] = """from .decision import ExecutiveDecision, DecisionContext

class ExecutivePolicies:
    def evaluate(self, context: DecisionContext) -> ExecutiveDecision | None:
        if context.risk > 0.9:
            return ExecutiveDecision.ESCALATE
        if context.confidence < 0.2:
            return ExecutiveDecision.CLARIFY
        if context.urgency > 0.8:
            return ExecutiveDecision.PROCEED
        return None
"""

files["interrupt.py"] = """from core.events.bus import EventBus
from core.models import Event

class InterruptHandler:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    async def interrupt(self, reason: str) -> None:
        await self.event_bus.publish_async(Event(
            topic="executive.interrupt",
            payload={"reason": reason, "action": "PAUSE_ALL"}
        ))
"""

files["arbitration.py"] = """from .decision import ExecutiveDecision

class ConflictArbitrator:
    def resolve(self, recommendations: dict[str, ExecutiveDecision]) -> ExecutiveDecision:
        # Hierarchy: ESCALATE > CANCEL > PAUSE > CLARIFY > DEFER > DELEGATE > RESUME > PROCEED
        hierarchy = {
            ExecutiveDecision.ESCALATE: 8,
            ExecutiveDecision.CANCEL: 7,
            ExecutiveDecision.PAUSE: 6,
            ExecutiveDecision.CLARIFY: 5,
            ExecutiveDecision.DEFER: 4,
            ExecutiveDecision.DELEGATE: 3,
            ExecutiveDecision.RESUME: 2,
            ExecutiveDecision.PROCEED: 1
        }
        
        if not recommendations:
            return ExecutiveDecision.PROCEED
            
        best = ExecutiveDecision.PROCEED
        best_score = 0
        
        for decision in recommendations.values():
            score = hierarchy.get(decision, 0)
            if score > best_score:
                best_score = score
                best = decision
                
        return best
"""

files["confidence.py"] = """class ConfidenceEstimator:
    def estimate(self, data_points: int, historical_success: float) -> float:
        if data_points == 0:
            return 0.1
        base = historical_success
        bonus = min(data_points * 0.05, 0.4)
        return min(base + bonus, 1.0)
"""

files["reflection.py"] = """from .decision import DecisionContext, ExecutiveDecision

class ReflectionEngine:
    def __init__(self) -> None:
        self.history: list[dict] = []

    def reflect(self, context: DecisionContext, decision: ExecutiveDecision, outcome: str) -> None:
        self.history.append({
            "context": context.to_dict(),
            "decision": decision.value,
            "outcome": outcome
        })
"""

files["manager.py"] = """from typing import Any

from core.events.bus import EventBus
from core.models import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .decision import ExecutiveDecision, DecisionContext
from .attention import AttentionSystem
from .priorities import PriorityManager
from .policies import ExecutivePolicies
from .interrupt import InterruptHandler
from .arbitration import ConflictArbitrator
from .confidence import ConfidenceEstimator
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
"""

files["__init__.py"] = """from .manager import ExecutiveManager
from .decision import ExecutiveDecision, DecisionContext
from .attention import AttentionSystem, AttentionState

__all__ = [
    "ExecutiveManager",
    "ExecutiveDecision",
    "DecisionContext",
    "AttentionSystem",
    "AttentionState"
]
"""

for fname, fcontent in files.items():
    with open(os.path.join(d, fname), "w") as f:
        f.write(fcontent)

tests_file = """import pytest

from core.events.bus import EventBus
from core.executive import ExecutiveManager, ExecutiveDecision, DecisionContext

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
def executive(event_bus):
    return ExecutiveManager(event_bus)

@pytest.mark.asyncio
async def test_decision_arbitration(executive):
    recs = {
        "memory": ExecutiveDecision.PROCEED,
        "reasoning": ExecutiveDecision.CLARIFY,
        "planner": ExecutiveDecision.DEFER
    }
    
    ctx = DecisionContext(goal_id="g1", confidence=0.8, risk=0.1, urgency=0.5)
    
    decision = await executive.evaluate_context(ctx, recs)
    # CLARIFY is highest in recs
    assert decision == ExecutiveDecision.CLARIFY

@pytest.mark.asyncio
async def test_policy_override(executive):
    recs = {
        "memory": ExecutiveDecision.PROCEED,
        "reasoning": ExecutiveDecision.PROCEED
    }
    
    # High risk should trigger ESCALATE policy, overriding recs
    ctx = DecisionContext(goal_id="g2", confidence=0.9, risk=0.95, urgency=0.5)
    decision = await executive.evaluate_context(ctx, recs)
    
    assert decision == ExecutiveDecision.ESCALATE

@pytest.mark.asyncio
async def test_attention_switching(executive):
    executive.attention.update(focus="high_prio_task", urgency=0.9)
    assert executive.attention.state.focus == "high_prio_task"
    assert executive.attention.state.urgency == 0.9

@pytest.mark.asyncio
async def test_interrupt_handling(executive):
    # Setup dummy subscription
    events_received = []
    def handler(event):
        events_received.append(event)
        
    executive.event_bus.subscribe("executive.interrupt", handler)
    
    await executive.interrupt_handler.interrupt("System critical")
    
    assert len(events_received) == 1
    assert events_received[0].payload["action"] == "PAUSE_ALL"

@pytest.mark.asyncio
async def test_reflection(executive):
    ctx = DecisionContext(goal_id="g3", confidence=0.5, risk=0.2, urgency=0.1)
    executive.record_outcome(ctx, ExecutiveDecision.PROCEED, "success")
    
    assert len(executive.reflection.history) == 1
    assert executive.reflection.history[0]["outcome"] == "success"
    assert executive.reflection.history[0]["decision"] == "PROCEED"
"""

with open("tests/test_executive.py", "w") as f:
    f.write(tests_file)
