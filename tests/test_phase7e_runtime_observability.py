"""
Tests for Phase 7E Runtime Observability & Trace Integrity.

Covers the 18 specific requirements:
1. every Agent.run gets request_id
2. request_id persists across loop iterations
3. model calls share request_id
4. tool calls share request_id
5. policy events share request_id
6. verification shares request_id
7. final trace is complete
8. failed tool produces failure event
9. timeout produces timeout event
10. denied policy action produces deny event
11. confirmation-required action records confirmation state
12. context truncation is recorded
13. mission verification status is recorded
14. CHAT produces lightweight trace
15. MEMORY produces lightweight trace
16. multi-step mission produces complete ordered trace
17. secrets are not emitted
18. no duplicate trace IDs within one request
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch
import pytest

from core.agent import Agent
from core.context_budget import ContextBudget
from core.cognition.context import ShortTermContext
from core.cognition.context_orchestrator import ContextOrchestrator
from core.cognition.conversation import ConversationEngine, ConversationResponse
from core.cognition.dialogue import DialogueState
from core.cognition.manager import CognitiveManager
from core.execution_policy import ExecutionPolicy, PolicyContext, PolicyVerdict
from core.identity.manager import IdentityManager
from core.mission_verifier import MissionCompletionVerifier, VerificationResult, VerificationStatus
from core.routing.intent_classifier import IntentClassifier, IntentType
from core.runtime_trace import (
    RequestTrace,
    sanitize_telemetry_value,
    get_current_trace,
    set_current_trace,
    reset_current_trace,
)
from core.task import Task, TaskStatus
from core.tool_feedback_loop import ToolFeedbackLoop
from providers.base_provider import BaseProvider
from providers.capabilities import Capability
from providers.provider_models import ModelResponse, TokenUsage


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


class MockTraceProvider(BaseProvider):
    def __init__(self, responses: list[str] | None = None):
        self._responses = list(responses or ['{"type": "RESPONSE", "message": "Test response."}'])
        self.call_count = 0

    @property
    def provider_id(self) -> str:
        return "mock_trace"

    @property
    def display_name(self) -> str:
        return "Mock Trace Provider"

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset([Capability.CHAT, Capability.TOOL_USE])

    @property
    def is_local(self) -> bool:
        return True

    def initialize(self) -> None:
        pass

    def generate(self, system_prompt: str, user_prompt: str, requirements=None) -> ModelResponse:
        self.call_count += 1
        resp_text = self._responses.pop(0) if self._responses else '{"type": "RESPONSE", "message": "Done."}'
        return ModelResponse(
            text=resp_text,
            provider_id="mock_trace",
            model_id="mock-qwen",
            latency_ms=15,
            token_usage=TokenUsage(input_tokens=len(user_prompt) // 4, output_tokens=10),
        )

    def embed(self, text: str, requirements=None):
        raise NotImplementedError()

    def estimate_cost(self, prompt: str, response: str) -> float:
        return 0.0

    def health_check(self):
        from providers.provider_models import ProviderHealthStatus
        return ProviderHealthStatus.HEALTHY

    def shutdown(self) -> None:
        pass


def build_test_trace_agent(provider: MockTraceProvider | None = None, executor_func=None) -> Agent:
    prov = provider or MockTraceProvider()

    cog_manager = MagicMock()
    def _proc_fast(msg, intent="chat"):
        res = prov.generate("", msg)
        import json
        try:
            data = json.loads(res.text)
        except Exception:
            data = {"type": "RESPONSE", "message": res.text}
        return ConversationResponse(
            type=data.get("type", "RESPONSE"),
            message=data.get("message", "Done."),
            tool=data.get("tool"),
            action=data.get("action"),
            parameters=data.get("parameters", {}),
        )
    cog_manager.process_fast.side_effect = _proc_fast
    cog_manager.last_context_budget = None

    validator = MagicMock()
    validator.validate.side_effect = lambda t: t

    executor = MagicMock()
    if executor_func:
        executor.execute.side_effect = executor_func
    else:
        def _default_exec(t: Task) -> Task:
            if t.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                t.start()
            t.complete("Execution succeeded.")
            return t
        executor.execute.side_effect = _default_exec

    policy = ExecutionPolicy(allow_destructive_from_core=False)
    classifier = IntentClassifier()

    planner = MagicMock()
    planner.plan.return_value = [
        Task(tool="system", action="respond", args={"message": "I'll do that."}),
        Task(tool="file", action="read_file", args={"path": "test.txt"}),
    ]

    verifier = MissionCompletionVerifier()

    agent = Agent(
        planner=planner,
        validator=validator,
        executor=executor,
        cognitive_manager=cog_manager,
        execution_policy=policy,
        mission_verifier=verifier,
    )
    return agent


# ---------------------------------------------------------------------------
# The 18 Required Tests for Phase 7E
# ---------------------------------------------------------------------------


class TestPhase7ERuntimeObservability:

    # 1. every Agent.run gets request_id
    def test_1_every_agent_run_gets_request_id(self):
        agent = build_test_trace_agent()
        tasks = agent.run("Hello there!", intent=IntentType.CHAT)

        trace = agent.last_trace
        assert trace is not None
        assert isinstance(trace.request_id, str)
        assert trace.request_id.startswith("req_")
        assert len(trace.request_id) > 6

    # 2. request_id persists across loop iterations
    def test_2_request_id_persists_across_loop_iterations(self):
        # Multi-turn tool feedback loop
        p = MockTraceProvider(responses=[
            '{"type": "ACTION", "tool": "file", "action": "create_file", "parameters": {"path": "a.txt"}}',
            '{"type": "ACTION", "tool": "file", "action": "read_file", "parameters": {"path": "a.txt"}}',
            '{"type": "RESPONSE", "message": "All done."}',
        ])
        agent = build_test_trace_agent(provider=p)

        agent.run("Create a.txt and read it.", intent=IntentType.TOOL)
        trace = agent.last_trace

        assert trace is not None
        req_id = trace.request_id

        # Tool calls must all share this request_id
        assert len(trace.tool_calls) >= 2
        for tc in trace.tool_calls:
            assert tc.request_id == req_id

        # Loop iteration events must all share this request_id
        loop_events = [e for e in trace.events if "loop_iteration" in e.event_type]
        assert len(loop_events) >= 2
        for le in loop_events:
            assert le.request_id == req_id

    # 3. model calls share request_id
    def test_3_model_calls_share_request_id(self):
        p = MockTraceProvider(responses=[
            '{"type": "ACTION", "tool": "file", "action": "create_file", "parameters": {"path": "b.txt"}}',
            '{"type": "RESPONSE", "message": "Done."}',
        ])
        agent = build_test_trace_agent(provider=p)

        agent.run("Create file b.txt", intent=IntentType.TOOL)
        trace = agent.last_trace

        assert trace is not None
        # All recorded model calls must have trace.request_id
        for mc in trace.llm_calls:
            assert mc.request_id == trace.request_id

    # 4. tool calls share request_id
    def test_4_tool_calls_share_request_id(self):
        agent = build_test_trace_agent()
        agent.run("Open notepad", intent=IntentType.TOOL)

        trace = agent.last_trace
        assert trace is not None
        assert len(trace.tool_calls) > 0
        for tc in trace.tool_calls:
            assert tc.request_id == trace.request_id

    # 5. policy events share request_id
    def test_5_policy_events_share_request_id(self):
        p = MockTraceProvider(responses=[
            '{"type": "ACTION", "tool": "file", "action": "read_file", "parameters": {"path": "test.txt"}}',
            '{"type": "RESPONSE", "message": "Done."}',
        ])
        agent = build_test_trace_agent(provider=p)
        agent.run("Read file test.txt", intent=IntentType.TOOL)

        trace = agent.last_trace
        assert trace is not None
        assert len(trace.policy_decisions) > 0
        for pd in trace.policy_decisions:
            assert pd.request_id == trace.request_id

    # 6. verification shares request_id
    def test_6_verification_shares_request_id(self):
        agent = build_test_trace_agent()
        agent.run("Autonomous mission: read test.txt", intent=IntentType.MISSION)

        trace = agent.last_trace
        assert trace is not None
        assert trace.verification_result is not None
        assert trace.verification_result["request_id"] == trace.request_id
        assert trace.mission_telemetry is not None
        assert trace.mission_telemetry["request_id"] == trace.request_id

    # 7. final trace is complete
    def test_7_final_trace_is_complete(self):
        agent = build_test_trace_agent()
        agent.run("Explain how a transistor works.", intent=IntentType.CHAT)

        trace = agent.last_trace
        assert trace is not None
        s = trace.summary()

        assert "request_id" in s
        assert "route" in s
        assert "model_calls" in s
        assert "tool_calls" in s
        assert "iterations" in s
        assert "verification" in s
        assert "context_truncated" in s
        assert "latency_ms" in s
        assert "status" in s

        # format_summary produces readable text
        txt = trace.format_summary()
        assert f"request_id: {s['request_id']}" in txt
        assert "route: CHAT" in txt

    # 8. failed tool produces failure event
    def test_8_failed_tool_produces_failure_event(self):
        def _failing_exec(t: Task) -> Task:
            if t.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                t.start()
            t.fail("Disk I/O error")
            return t

        p = MockTraceProvider(responses=[
            '{"type": "ACTION", "tool": "file", "action": "read_file", "parameters": {"path": "broken.txt"}}',
            '{"type": "RESPONSE", "message": "Done."}',
        ])
        agent = build_test_trace_agent(provider=p, executor_func=_failing_exec)
        agent.run("Read file broken.txt", intent=IntentType.TOOL)

        trace = agent.last_trace
        assert trace is not None
        failed_tools = [tc for tc in trace.tool_calls if tc.execution_status == "failed"]
        assert len(failed_tools) > 0
        assert failed_tools[0].error_message is not None

        # failure_summary accurately reconstructs the failure
        diag = trace.failure_summary()
        assert diag["failed"] is True
        assert diag["stage"] == "tool_execution"

    # 9. timeout produces timeout event
    def test_9_timeout_produces_timeout_event(self):
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        def _timing_out_exec(t: Task) -> Task:
            raise FuturesTimeoutError("Operation timed out")

        p = MockTraceProvider(responses=[
            '{"type": "ACTION", "tool": "file", "action": "read_file", "parameters": {"path": "slow.txt"}}',
            '{"type": "RESPONSE", "message": "Done."}',
        ])
        agent = build_test_trace_agent(provider=p, executor_func=_timing_out_exec)
        agent.run("Read slow.txt", intent=IntentType.TOOL)

        trace = agent.last_trace
        assert trace is not None
        timed_out = [tc for tc in trace.tool_calls if tc.timeout is True]
        assert len(timed_out) > 0
        assert timed_out[0].error_category == "Timeout"

        diag = trace.failure_summary()
        assert diag["timeout_occurred"] is True
        assert diag["stage"] == "timeout"

    # 10. denied policy action produces deny event
    def test_10_denied_policy_action_produces_deny_event(self):
        p = MockTraceProvider(responses=[
            '{"type": "ACTION", "tool": "file", "action": "format_disk", "parameters": {"disk": "C:"}}',
            '{"type": "RESPONSE", "message": "Done."}',
        ])
        agent = build_test_trace_agent(provider=p)

        agent.run("Format the disk", intent=IntentType.TOOL)
        trace = agent.last_trace

        assert trace is not None
        denied_decisions = [pd for pd in trace.policy_decisions if pd.verdict == "deny"]
        assert len(denied_decisions) > 0
        assert "format_disk" in denied_decisions[0].action

        diag = trace.failure_summary()
        assert diag["stage"] == "policy"
        assert diag["policy_verdict"] == "deny"

    # 11. confirmation-required action records confirmation state
    def test_11_confirmation_required_action_records_confirmation_state(self):
        policy = ExecutionPolicy(allow_destructive_from_core=True)
        p = MockTraceProvider(responses=[
            '{"type": "ACTION", "tool": "file", "action": "delete_file", "parameters": {"path": "important.txt"}}',
            '{"type": "RESPONSE", "message": "Done."}',
        ])
        agent = build_test_trace_agent(provider=p)
        agent._execution_policy = policy

        agent.run("Delete important.txt", intent=IntentType.TOOL, user_confirmed=False)
        trace = agent.last_trace

        assert trace is not None
        req_conf = [tc for tc in trace.tool_calls if tc.confirmation_required is True]
        assert len(req_conf) > 0
        assert req_conf[0].policy_verdict == "require_confirmation"
        assert req_conf[0].confirmation_status == "denied"

    # 12. context truncation is recorded
    def test_12_context_truncation_is_recorded(self):
        agent = build_test_trace_agent()
        # Simulate an execution that generated a truncated ContextBudget
        budget = ContextBudget(truncated=True, truncation_reason="tool_result_exceeded")
        agent._cognitive_manager.last_context_budget = budget

        agent.run("Tell me something", intent=IntentType.CHAT)
        trace = agent.last_trace

        assert trace is not None
        assert trace.context_budget is not None
        # Summary captures context_truncated
        assert trace.summary()["context_truncated"] is True

    # 13. mission verification status is recorded
    def test_13_mission_verification_status_is_recorded(self):
        agent = build_test_trace_agent()
        agent.run("Autonomous mission: read file", intent=IntentType.MISSION)

        trace = agent.last_trace
        assert trace is not None
        assert trace.verification_result is not None
        assert trace.verification_result["status"] in ("passed", "failed", "partial")

    # 14. CHAT produces lightweight trace
    def test_14_chat_produces_lightweight_trace(self):
        agent = build_test_trace_agent()
        agent.run("What is quantum computing?", intent=IntentType.CHAT)

        trace = agent.last_trace
        assert trace is not None
        assert trace.route == "CHAT"
        assert len(trace.tool_calls) == 0
        assert trace.summary()["tool_calls"] == 0
        assert trace.summary()["iterations"] == 0

    # 15. MEMORY produces lightweight trace
    def test_15_memory_produces_lightweight_trace(self):
        agent = build_test_trace_agent()
        agent.run("Remember that my name is Alice.", intent=IntentType.MEMORY)

        trace = agent.last_trace
        assert trace is not None
        assert trace.route == "MEMORY"
        assert len(trace.tool_calls) == 0
        assert trace.summary()["latency_ms"] < 1000

    # 16. multi-step mission produces complete ordered trace
    def test_16_multistep_mission_produces_complete_ordered_trace(self):
        agent = build_test_trace_agent()
        agent.run("Autonomous mission: complete workflow", intent=IntentType.MISSION)

        trace = agent.last_trace
        assert trace is not None

        # Verify timestamp ordering across events
        timestamps = [e.monotonic_time for e in trace.events]
        assert timestamps == sorted(timestamps)

        # Event sequence must include request_received, route_classified, mission_verified, request_completed
        event_types = [e.event_type for e in trace.events]
        assert "request_received" in event_types
        assert "route_classified" in event_types
        assert "mission_verified" in event_types
        assert "request_completed" in event_types

        # request_received must precede request_completed
        assert event_types.index("request_received") < event_types.index("request_completed")

    # 17. secrets are not emitted
    def test_17_secrets_are_not_emitted(self):
        secret_payload = {
            "password": "SUPER_SECRET_PASSWORD_123",
            "api_key": "sk-live-1234567890abcdef123456",
            "token": "bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret",
            "safe_key": "safe_value",
        }
        sanitized = sanitize_telemetry_value(secret_payload)

        assert sanitized["password"] == "********"
        assert sanitized["api_key"] == "********"
        assert sanitized["token"] == "********"
        assert sanitized["safe_key"] == "safe_value"

        # In string form
        raw_str = "Authorization: Bearer mysecrettoken123456789"
        sanitized_str = sanitize_telemetry_value(raw_str)
        assert "mysecrettoken123456789" not in sanitized_str
        assert "Bearer ********" in sanitized_str

    # 18. no duplicate trace IDs within one request
    def test_18_no_duplicate_trace_ids_within_one_request(self):
        agent = build_test_trace_agent()
        agent.run("Autonomous mission: run multiple steps", intent=IntentType.MISSION)

        trace = agent.last_trace
        assert trace is not None

        event_ids = [e.event_id for e in trace.events]
        assert len(event_ids) == len(set(event_ids))

        tool_call_ids = [t.call_id for t in trace.tool_calls]
        assert len(tool_call_ids) == len(set(tool_call_ids))

        policy_ids = [p.decision_id for p in trace.policy_decisions]
        assert len(policy_ids) == len(set(policy_ids))
