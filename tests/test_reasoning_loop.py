import pytest
from unittest.mock import MagicMock
from core.reasoning.loop import ReasoningLoop
from core.reasoning.execution_plan import ExecutionPlan
from core.cognition.context import ShortTermContext

def test_reasoning_loop_success():
    # Setup
    mock_llm = MagicMock()
    mock_registry = MagicMock()
    
    # Mock LLM Planner (iteration 1)
    mock_planner_response = MagicMock()
    mock_planner_response.text = '{"ordered_steps": ["step1"], "required_tools": ["valid_tool"]}'
    
    # Mock LLM Critic (iteration 1)
    mock_critic_response = MagicMock()
    mock_critic_response.text = '{"is_complete": true, "needs_clarification": false}'
    
    mock_llm.generate.side_effect = [mock_planner_response, mock_critic_response]
    
    # Mock Tool Registry
    mock_registry.list_tools.return_value = ["valid_tool"]
    
    loop = ReasoningLoop(mock_llm, mock_registry)
    ctx = ShortTermContext()
    
    plan = loop.run("Do something", ctx)
    
    assert "step1" in plan.ordered_steps
    assert "valid_tool" in plan.required_tools

def test_reasoning_loop_revise_and_verify_failure():
    # Setup
    mock_llm = MagicMock()
    mock_registry = MagicMock()
    
    # Iteration 1
    mock_planner_response_1 = MagicMock()
    mock_planner_response_1.text = '{"ordered_steps": ["step1"], "required_tools": ["invalid_tool"]}'
    
    mock_critic_response_1 = MagicMock()
    mock_critic_response_1.text = '{"is_complete": false, "feedback": "Missing something", "needs_clarification": false}'
    
    # Iteration 2 (Critic requested revise, now planner generates new plan)
    mock_planner_response_2 = MagicMock()
    mock_planner_response_2.text = '{"ordered_steps": ["step1", "step2"], "required_tools": ["invalid_tool"]}'
    
    mock_critic_response_2 = MagicMock()
    mock_critic_response_2.text = '{"is_complete": true, "needs_clarification": false}'
    
    # Iteration 3 (Verifier fails, planner revises again)
    mock_planner_response_3 = MagicMock()
    mock_planner_response_3.text = '{"ordered_steps": ["step1", "step2"], "required_tools": ["valid_tool"]}'
    
    mock_critic_response_3 = MagicMock()
    mock_critic_response_3.text = '{"is_complete": true, "needs_clarification": false}'
    
    mock_llm.generate.side_effect = [
        mock_planner_response_1, mock_critic_response_1, # It 1
        mock_planner_response_2, mock_critic_response_2, # It 2
        mock_planner_response_3, mock_critic_response_3  # It 3
    ]
    
    mock_registry.list_tools.return_value = ["valid_tool"]
    
    loop = ReasoningLoop(mock_llm, mock_registry)
    ctx = ShortTermContext()
    
    plan = loop.run("Do something complex", ctx, max_iterations=4)
    
    assert "step2" in plan.ordered_steps
    assert "valid_tool" in plan.required_tools
