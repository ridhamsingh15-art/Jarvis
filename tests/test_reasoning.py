import pytest

from core.events.bus import EventBus
from core.reasoning import Entity, EntityType, Hypothesis, ReasoningManager


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
