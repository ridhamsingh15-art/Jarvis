import pytest
from unittest.mock import MagicMock
from core.executive.models import ExecutionStrategy, GoalType, Complexity
from core.executive.reasoning import ReasoningEngine
from core.executive.model_selection import ModelSelection
from core.cognition.context import ShortTermContext
from providers.capabilities import Capability

def test_reasoning_engine():
    mock_llm = MagicMock()
    mock_response = MagicMock()
    # Mock LLM returning JSON matching the schema
    mock_response.text = '{"goal": "coding", "complexity": "complex", "requires_tools": true, "requires_clarification": false}'
    mock_llm.generate.return_value = mock_response
    
    engine = ReasoningEngine(mock_llm)
    ctx = ShortTermContext()
    
    strategy = engine.analyze("Write a python script", ctx)
    
    assert strategy.goal == GoalType.CODING
    assert strategy.complexity == Complexity.COMPLEX
    assert strategy.requires_tools is True
    assert strategy.requires_clarification is False

def test_model_selection():
    selection = ModelSelection()
    
    strategy = ExecutionStrategy(goal=GoalType.RESEARCH, complexity=Complexity.VERY_COMPLEX)
    reqs = selection.apply_selection(strategy)
    
    assert Capability.REASONING in reqs.capabilities
    assert reqs.task_complexity == 9
    assert reqs.prefer_local is False
    
    strategy2 = ExecutionStrategy(goal=GoalType.CONVERSATION, complexity=Complexity.SIMPLE)
    reqs2 = selection.apply_selection(strategy2)
    
    assert Capability.CHAT in reqs2.capabilities
    assert reqs2.task_complexity == 3
    assert reqs2.prefer_local is True
