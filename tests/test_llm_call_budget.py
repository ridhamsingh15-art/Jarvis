"""
LLM Call Budget Tests.

Asserts the maximum number of LLM calls allowed per route.

Policy:
  CHAT (RESPONSE)     → 1 call  (ConversationEngine only)
  MEMORY write        → 0 calls (deterministic key/value extraction)
  TOOL with ACTION    → 1 call  (ConversationEngine only)
  CHAT → reflection   → 0 extra (reflection skipped for pure RESPONSE)
  TOOL → reflection   → 0 extra (reflection only if tool actually fires)

These tests verify the agent does NOT make unnecessary LLM calls.
The reflection subsystem is NOT removed — just not called for simple turns.
"""

import json
import pytest
from unittest.mock import MagicMock, call, patch, Mock
from providers.provider_models import ModelResponse
from core.agent import Agent
from core.cognition.conversation import ConversationResponse
from core.routing.intent_classifier import IntentType
from core.task import TaskStatus


# ─── Test utilities ────────────────────────────────────────────────────────

def _mock_llm(response_text: str):
    """Return an LLMClient mock counting generate() calls."""
    llm = MagicMock()
    llm.generate.return_value = ModelResponse(
        text=response_text, provider_id="mock", model_id="mock", latency_ms=1
    )
    return llm


def _make_agent_with_intent(intent: IntentType, process_fast_response: ConversationResponse):
    """Build a minimal Agent with a patched IntentClassifier."""
    cognitive = MagicMock()
    cognitive.process_fast.return_value = process_fast_response
    cognitive.process.return_value = process_fast_response

    agent = Agent(
        planner=MagicMock(),
        validator=MagicMock(),
        executor=MagicMock(),
        cognitive_manager=cognitive,
    )
    # Patch the classifier so we control routing
    agent._intent_classifier = MagicMock()
    agent._intent_classifier.classify.return_value = intent
    # Prevent actual task processing side-effects
    agent._process_task = lambda t: t
    return agent, cognitive


# ─── Phase 2 reflection gate tests ──────────────────────────────────────────

class TestReflectionGate:

    def test_chat_response_does_not_trigger_reflection(self):
        """Pure CHAT RESPONSE: reflect() must NOT be called on CognitiveManager."""
        agent, cognitive = _make_agent_with_intent(
            intent=IntentType.CHAT,
            process_fast_response=ConversationResponse(
                type="RESPONSE", message="Hi there!"
            ),
        )
        agent.run("Hi")
        # reflect() is the CognitiveManager method Agent calls
        cognitive.reflect.assert_not_called()

    def test_tool_execution_triggers_reflect(self):
        """When a tool is successfully executed, reflect() IS called."""
        response = ConversationResponse(
            type="ACTION", message="Opening calc.",
            tool="windows", action="open_app", parameters={"app": "calculator"}
        )
        agent, cognitive = _make_agent_with_intent(IntentType.TOOL, response)

        # Make executor succeed
        def fake_execute(task):
            task.start()
            task.complete("Opened")
            return task
        agent._executor.execute.side_effect = fake_execute

        agent.run("Open calculator")
        # reflect() should be called because tool_action was set
        cognitive.reflect.assert_called_once()

    def test_memory_write_no_reflection(self):
        """MEMORY write: no reflection LLM call."""
        agent, cognitive = _make_agent_with_intent(
            intent=IntentType.MEMORY,
            process_fast_response=ConversationResponse(type="RESPONSE", message="ok"),
        )
        mock_memory = MagicMock()
        agent._memory = mock_memory

        agent.run("Remember that my name is Ridham")
        cognitive.reflect.assert_not_called()


# ─── Phase 3 deterministic context tests ────────────────────────────────────

class TestContextBuilderNeverCallsLLM:

    def test_chat_intent_no_llm_in_context_builder(self):
        """ContextBuilder.determine_providers() must not call any LLM."""
        from core.cognition.context_builder import ContextBuilder
        builder = ContextBuilder()
        # The builder must not have an _llm attribute at all
        assert not hasattr(builder, "_llm")
        # Calling it multiple times with different intents is safe
        for intent in ("chat", "tool", "memory", "mission"):
            providers = builder.determine_providers(intent=intent)
            assert len(providers) > 0


# ─── Phase 4 classifier budget tests ────────────────────────────────────────

class TestIntentClassifierBudget:

    def test_greeting_zero_llm_calls(self):
        """Stage 1 matches 'Hi' → zero LLM calls."""
        from core.cognition.context_builder import ContextBuilder
        from core.routing.intent_classifier import IntentClassifier
        llm = _mock_llm("CHAT")
        classifier = IntentClassifier(llm_client=llm)
        result = classifier.classify("Hi")
        assert result == IntentType.CHAT
        llm.generate.assert_not_called()

    def test_memory_pattern_zero_llm_calls(self):
        """'Remember my name' → Stage 1 match → zero LLM calls."""
        from core.routing.intent_classifier import IntentClassifier
        llm = _mock_llm("MEMORY")
        classifier = IntentClassifier(llm_client=llm)
        result = classifier.classify("Remember that my name is Ridham")
        assert result == IntentType.MEMORY
        llm.generate.assert_not_called()

    def test_mission_pattern_zero_llm_calls(self):
        """Clear MISSION keywords → Stage 1 match → zero LLM calls."""
        from core.routing.intent_classifier import IntentClassifier
        llm = _mock_llm("MISSION")
        classifier = IntentClassifier(llm_client=llm)
        result = classifier.classify("Create a SaaS application")
        assert result == IntentType.MISSION
        llm.generate.assert_not_called()

    def test_ambiguous_triggers_exactly_one_llm_call(self):
        """Ambiguous input → Stage 2 fires exactly once."""
        from core.routing.intent_classifier import IntentClassifier
        llm = _mock_llm("CHAT")
        classifier = IntentClassifier(llm_client=llm)
        # "Why is the sky blue?" has no deterministic match
        classifier.classify("Why is the sky blue?")
        llm.generate.assert_called_once()

    def test_stage2_llm_failure_defaults_to_chat(self):
        """If Stage 2 LLM fails, fall back to CHAT — never crash."""
        from core.routing.intent_classifier import IntentClassifier
        llm = MagicMock()
        llm.generate.side_effect = RuntimeError("LLM is down")
        classifier = IntentClassifier(llm_client=llm)
        result = classifier.classify("Why is the sky blue?")
        assert result == IntentType.CHAT


# ─── Phase 5 style extraction tests ─────────────────────────────────────────

class TestCapabilityPlanStyle:

    def test_style_field_defaults_to_storytelling(self):
        """CapabilityPlan.style defaults to 'storytelling'."""
        from core.capability.models import CapabilityPlan
        plan = CapabilityPlan(reasoning_model="auto")
        assert plan.style == "storytelling"

    def test_planner_maps_style_from_json(self):
        """CapabilityPlanner maps 'style' from raw LLM output."""
        from core.capability.planner import CapabilityPlanner
        raw = {
            "reasoning_model": "auto",
            "required_capabilities": [],
            "required_tools": [],
            "style": "educational",
            "confidence": 0.9,
        }
        plan = CapabilityPlanner().build_plan(raw)
        assert plan.style == "educational"

    def test_planner_defaults_style_when_absent(self):
        """If LLM omits 'style', CapabilityPlanner defaults to 'storytelling'."""
        from core.capability.planner import CapabilityPlanner
        raw = {"reasoning_model": "auto", "required_capabilities": []}
        plan = CapabilityPlanner().build_plan(raw)
        assert plan.style == "storytelling"
