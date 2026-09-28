"""
Phase D + D2 Tests — LLM Observability & Budgets

Tests:
1. track() records a successful call
2. track() records a failed call
3. budget passes for valid stage calls
4. budget exhausted for stage
5. total budget exhausted
6. CHAT budget: classifier=1, conversation=1, total=2
7. MISSION budget: higher limits
8. Stage budget for unknown stage defaults to 1
9. Summary captures correct counts
10. Correlation IDs flow through records
"""
import pytest
from core.llm_observability import (
    LLMObservability,
    LLMCallRecord,
    LLMBudget,
    CHAT_BUDGET,
    MISSION_BUDGET,
    TOOL_BUDGET,
    MEMORY_BUDGET,
)


class TestLLMObservabilityTracking:
    def test_successful_call_recorded(self):
        obs = LLMObservability(request_id="r1", route="chat")
        with obs.track("conversation", provider="ollama", model="qwen3") as rec:
            rec.success = True
            rec.input_tokens = 50
            rec.output_tokens = 100
        assert obs.total_calls == 1
        summary = obs.summary()
        assert summary["total_calls"] == 1
        assert summary["succeeded"] == 1
        assert summary["failed"] == 0

    def test_failed_call_recorded(self):
        obs = LLMObservability(request_id="r2", route="chat")
        with pytest.raises(RuntimeError):
            with obs.track("conversation") as rec:
                raise RuntimeError("LLM down")
        assert obs.total_calls == 1
        summary = obs.summary()
        assert summary["failed"] == 1

    def test_multiple_stages_tracked(self):
        obs = LLMObservability(request_id="r3", route="mission")
        for stage in ["classifier", "capability", "planner", "reasoning"]:
            with obs.track(stage) as rec:
                rec.success = True
        assert obs.total_calls == 4
        assert obs.summary()["stage_counts"]["classifier"] == 1
        assert obs.summary()["stage_counts"]["reasoning"] == 1

    def test_correlation_ids_flow(self):
        obs = LLMObservability(
            request_id="req-x",
            conversation_id="conv-y",
            mission_id="miss-z",
            route="mission",
        )
        with obs.track("reasoning") as rec:
            rec.success = True
        assert obs.request_id == "req-x"
        assert obs.conversation_id == "conv-y"
        assert obs.mission_id == "miss-z"


class TestLLMBudgetEnforcement:
    def test_chat_classifier_budget_one(self):
        obs = LLMObservability(request_id="b1", route="chat", budget=CHAT_BUDGET)
        # First classifier call: allowed
        assert obs.check_budget("classifier") is True
        with obs.track("classifier") as rec:
            rec.success = True
        # Second classifier call: budget exhausted
        assert obs.check_budget("classifier") is False

    def test_chat_total_budget(self):
        obs = LLMObservability(request_id="b2", route="chat", budget=CHAT_BUDGET)
        # CHAT total_max = 2
        for _ in range(CHAT_BUDGET.total_max):
            with obs.track("conversation") as rec:
                rec.success = True
        # Next call should be denied
        assert obs.check_budget("conversation") is False

    def test_mission_budget_higher(self):
        obs = LLMObservability(request_id="b3", route="mission", budget=MISSION_BUDGET)
        # reasoning_max = 3
        for _ in range(MISSION_BUDGET.reasoning_max):
            assert obs.check_budget("reasoning") is True
            with obs.track("reasoning") as rec:
                rec.success = True
        assert obs.check_budget("reasoning") is False

    def test_tool_loop_budget(self):
        obs = LLMObservability(request_id="b4", route="tool", budget=TOOL_BUDGET)
        # tool_loop_max = 3
        for _ in range(TOOL_BUDGET.tool_loop_max):
            assert obs.check_budget("tool_loop") is True
            with obs.track("tool_loop") as rec:
                rec.success = True
        assert obs.check_budget("tool_loop") is False

    def test_unknown_stage_defaults_to_one(self):
        budget = LLMBudget()
        assert budget.for_stage("nonexistent_stage") == 1

    def test_memory_budget_minimal(self):
        obs = LLMObservability(request_id="b5", route="memory", budget=MEMORY_BUDGET)
        # memory total_max = 1
        with obs.track("conversation") as rec:
            rec.success = True
        # No more budget
        assert obs.check_budget("conversation") is False


class TestLLMObservabilitySummary:
    def test_summary_structure(self):
        obs = LLMObservability(request_id="s1", route="chat")
        with obs.track("classifier") as rec:
            rec.success = True
        summary = obs.summary()
        assert "request_id" in summary
        assert "route" in summary
        assert "total_calls" in summary
        assert "succeeded" in summary
        assert "failed" in summary
        assert "total_latency_ms" in summary
        assert "stage_counts" in summary

    def test_latency_accumulated(self):
        obs = LLMObservability(request_id="s2", route="chat")
        with obs.track("conversation") as rec:
            rec.success = True
        assert obs.summary()["total_latency_ms"] >= 0
