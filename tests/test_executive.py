import pytest

from core.events.bus import EventBus
from core.executive import DecisionContext, ExecutiveDecision, ExecutiveManager


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
