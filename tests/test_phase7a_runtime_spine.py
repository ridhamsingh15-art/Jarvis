"""
Phase 7A Integration Test Suite — Runtime Execution Spine & Security Truthfulness.

Validates the end-to-end integration:
    Agent.run()
    -> Intent Classification
    -> Validation & Repair
    -> ExecutionPolicy (Mandatory Security Choke Point)
    -> Executor (Timeout-Guarded)
    -> Actual Tool
    -> Result Grounding & ExecutionSummary

Tests the 10 Phase 7A contracts:
1. allowed action reaches execution
2. denied action never reaches execution
3. confirmation-required action does not execute without user approval
4. model cannot self-authorize (MODEL != AUTHORIZATION)
5. tool failure remains grounded
6. successful tool remains grounded
7. telemetry reports actual components used
8. telemetry does not report unused mission components (used=False)
9. no-tool false success claim is rejected
10. timeout/failure is correctly represented
"""

from __future__ import annotations

import logging
import time
from unittest.mock import MagicMock

import pytest

from core.action_definition import ActionDefinition
from core.agent import Agent
from core.cognition.conversation import ConversationResponse
from core.execution_policy import (
    CapabilitySource,
    ExecutionPolicy,
    PolicyContext,
    PolicyVerdict,
)
from core.execution_summary import ExecutionSummary
from core.registry import Registry
from core.task import Task, TaskStatus
from core.validator import Validator
from main import build_agent
from tools.base_tool import BaseTool


# ---------------------------------------------------------------------------
# Test Helpers & Safe Fakes
# ---------------------------------------------------------------------------

class FakeTool(BaseTool):
    """Safe controllable tool for integration testing."""

    def __init__(self, name: str = "windows") -> None:
        self._name = name
        self.executed_actions: list[tuple[str, dict]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Fake controllable tool for tests"

    def get_actions(self) -> dict[str, ActionDefinition]:
        return {
            "open_app": ActionDefinition(
                name="open_app",
                description="Opens an app",
                required_args=[],
                optional_args=["app"],
            ),
            "shutdown": ActionDefinition(
                name="shutdown",
                description="Shutdown system",
                required_args=[],
                optional_args=["user_confirmed", "confirmed", "authorization", "bypass_policy"],
            ),
            "slow_action": ActionDefinition(
                name="slow_action",
                description="Slow action",
                required_args=[],
            ),
            "failing_action": ActionDefinition(
                name="failing_action",
                description="Failing action",
                required_args=[],
                optional_args=["app"],
            ),
        }

    def execute(self, action: str, args: dict) -> str:
        self.executed_actions.append((action, args))
        if action == "slow_action":
            time.sleep(0.5)
            return "slow result"
        if action == "failing_action":
            raise RuntimeError("Underlying tool failed")
        if action == "open_app":
            app = args.get("app", "application")
            if app == "broken_app":
                from core.exceptions import ExecutionError
                raise ExecutionError("App failed to start")
            return f"Opened {app} successfully"
        return f"{self._name}.{action} executed successfully"


class DirectExecutor:
    """Synchronous executor simulating ExecutionEngine without network/OS dependencies."""

    def __init__(self, tool: FakeTool) -> None:
        self.tool = tool
        self.call_count = 0

    def execute(self, task: Task) -> Task:
        self.call_count += 1
        if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
            task.start()
        try:
            res = self.tool.execute(task.action, task.args)
            task.complete(res)
        except Exception as exc:  # noqa: BLE001
            task.fail(str(exc))
        return task


def _build_test_agent(
    tool: FakeTool,
    policy: ExecutionPolicy | None = None,
    default_timeout: float = 5.0,
) -> tuple[Agent, DirectExecutor]:
    """Assemble an Agent with real Validator, ExecutionPolicy, and DirectExecutor."""
    registry = Registry()
    registry.register(tool)
    validator = Validator(registry)
    executor = DirectExecutor(tool)
    exec_policy = policy or ExecutionPolicy(allow_destructive_from_core=True)

    cognitive = MagicMock()
    planner = MagicMock()

    agent = Agent(
        planner=planner,
        validator=validator,
        executor=executor,
        cognitive_manager=cognitive,
        execution_policy=exec_policy,
        default_tool_timeout=default_timeout,
    )
    return agent, executor


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestPhase7ARuntimeSpine:
    """Tests the real Agent.run() execution spine against the 10 requirements."""

    def test_1_allowed_action_reaches_execution(self):
        """1. An allowed, safe tool action passes policy and reaches the Executor."""
        tool = FakeTool(name="windows")
        agent, executor = _build_test_agent(tool)

        agent._cognitive_manager.process_fast.return_value = ConversationResponse(
            type="ACTION",
            message="Opening the calculator.",
            tool="windows",
            action="open_app",
            parameters={"app": "calculator"},
        )

        tasks = agent.run("Open calculator")
        agent.close()

        # Tasks: [system.respond, windows.open_app]
        assert len(tasks) == 2
        tool_task = tasks[1]
        assert tool_task.status == TaskStatus.COMPLETED
        assert tool_task.result == "Opened calculator successfully"
        assert executor.call_count == 1
        assert len(tool.executed_actions) == 1
        assert tool.executed_actions[0][0] == "open_app"

    def test_2_denied_action_never_reaches_execution(self):
        """2. A policy-denied action fails at policy gate and NEVER reaches the Executor."""
        tool = FakeTool(name="windows")
        # Policy with strict restriction: allow_destructive_from_core=False
        strict_policy = ExecutionPolicy(allow_destructive_from_core=False)
        agent, executor = _build_test_agent(tool, policy=strict_policy)

        # Prompt attempting high-risk action that is denied under strict policy
        agent._cognitive_manager.process_fast.return_value = ConversationResponse(
            type="ACTION",
            message="Executing shutdown.",
            tool="windows",
            action="shutdown",
            parameters={},
        )

        tasks = agent.run("Shutdown system")
        agent.close()

        tool_task = tasks[1]
        assert tool_task.status == TaskStatus.FAILED
        assert "Execution policy denied" in tool_task.error
        # The executor and tool were NEVER called
        assert executor.call_count == 0
        assert len(tool.executed_actions) == 0

    def test_3_confirmation_required_action_requires_user_approval(self):
        """3. High-risk action fails without approval; executes when user_confirmed=True."""
        tool = FakeTool(name="windows")
        policy = ExecutionPolicy(allow_destructive_from_core=True)
        agent, executor = _build_test_agent(tool, policy=policy)

        agent._cognitive_manager.process_fast.return_value = ConversationResponse(
            type="ACTION",
            message="Shutting down.",
            tool="windows",
            action="shutdown",
            parameters={},
        )

        # Attempt A: Without user approval (default user_confirmed=False)
        tasks_denied = agent.run("Shutdown the machine", user_confirmed=False)
        assert tasks_denied[1].status == TaskStatus.FAILED
        assert "requires user confirmation" in tasks_denied[1].error
        assert executor.call_count == 0
        assert len(tool.executed_actions) == 0

        # Attempt B: With explicit user approval (user_confirmed=True)
        tasks_approved = agent.run("Shutdown the machine", user_confirmed=True)
        assert tasks_approved[1].status == TaskStatus.COMPLETED
        assert executor.call_count == 1
        assert len(tool.executed_actions) == 1
        agent.close()

    def test_4_model_cannot_self_authorize(self):
        """4. Security invariant: Model-generated confirmation string is NOT user confirmation."""
        tool = FakeTool(name="windows")
        policy = ExecutionPolicy(allow_destructive_from_core=True)
        agent, executor = _build_test_agent(tool, policy=policy)

        # Model tries to self-authorize by embedding approval flags in parameters
        agent._cognitive_manager.process_fast.return_value = ConversationResponse(
            type="ACTION",
            message="Shutting down with self-authorization.",
            tool="windows",
            action="shutdown",
            parameters={
                "user_confirmed": True,
                "confirmed": True,
                "authorization": "USER_APPROVED",
                "bypass_policy": True,
            },
        )

        # Caller did NOT confirm (user_confirmed=False)
        tasks = agent.run("Shutdown now", user_confirmed=False)
        agent.close()

        tool_task = tasks[1]
        assert tool_task.status == TaskStatus.FAILED
        assert "requires user confirmation" in tool_task.error
        # Model parameter was ignored; tool NEVER executed
        assert executor.call_count == 0
        assert len(tool.executed_actions) == 0

    def test_5_tool_failure_remains_grounded(self):
        """5. When a tool fails, response is grounded in the failure, rejecting any success hallucination."""
        tool = FakeTool(name="windows")
        agent, executor = _build_test_agent(tool)

        # Model falsely claims it succeeded in message
        agent._cognitive_manager.process_fast.return_value = ConversationResponse(
            type="ACTION",
            message="I successfully opened the application and it is now running.",
            tool="windows",
            action="open_app",
            parameters={"app": "broken_app"},
        )

        tasks = agent.run("Open broken_app")
        agent.close()

        resp_task = tasks[0]
        # Result grounding must discard the model's false success claim
        assert resp_task.status == TaskStatus.COMPLETED
        assert "couldn't complete windows.open_app" in resp_task.result
        assert "broken_app" in resp_task.result
        assert "successfully opened" not in resp_task.result.lower()

    def test_6_successful_tool_remains_grounded(self):
        """6. A successful tool execution grounds the response in the factual output."""
        tool = FakeTool(name="windows")
        agent, executor = _build_test_agent(tool)

        agent._cognitive_manager.process_fast.return_value = ConversationResponse(
            type="ACTION",
            message="Opening notepad.",
            tool="windows",
            action="open_app",
            parameters={"app": "notepad"},
        )

        tasks = agent.run("Open notepad")
        agent.close()

        resp_task = tasks[0]
        assert resp_task.status == TaskStatus.COMPLETED
        assert "Done — opened notepad." in resp_task.result
        assert agent.last_execution_summary.all_succeeded is True

    def test_7_telemetry_reports_actual_components_used(self, caplog):
        """7. Lifecycle telemetry reports actual call counts and latency without mock inflation."""
        tool = FakeTool(name="windows")
        agent, _ = _build_test_agent(tool)

        agent._cognitive_manager.process_fast.return_value = ConversationResponse(
            type="RESPONSE",
            message="Hello! How can I assist you?",
        )

        with caplog.at_level(logging.INFO):
            agent.run("Hello")
        agent.close()

        assert any("Lifecycle Metrics:" in r.message for r in caplog.records)
        assert any("llm_call_count=1" in r.message for r in caplog.records)

    def test_8_telemetry_does_not_report_unused_mission_components(self, caplog):
        """8. Telemetry for MISSION route truthfully reports executive_brain_used=False."""
        tool = FakeTool(name="windows")
        agent, _ = _build_test_agent(tool)

        agent._planner.plan.return_value = []
        agent._cognitive_manager.process.return_value = ConversationResponse(
            type="RESPONSE",
            message="Mission plan completed.",
        )

        with caplog.at_level(logging.INFO):
            agent.run("Research the history of computing")
        agent.close()

        # Must report SKIPPED, not ENABLED
        assert any("[ExecutiveBrain] SKIPPED" in r.message for r in caplog.records)
        assert any("[ReasoningLoop] SKIPPED" in r.message for r in caplog.records)
        assert any("[MissionControl] SKIPPED" in r.message for r in caplog.records)
        # Metrics must declare False
        assert any(
            "executive_brain_used=False, reasoning_loop_used=False, mission_control_used=False" in r.message
            for r in caplog.records
        )

    def test_9_no_tool_false_success_is_rejected(self):
        """9. When 0 tools execute, false model claims of action completion are rejected."""
        tool = FakeTool(name="windows")
        agent, _ = _build_test_agent(tool)

        # Model emits a pure conversational response claiming it opened calculator,
        # but generated ZERO executable tool tasks!
        agent._cognitive_manager.process_fast.return_value = ConversationResponse(
            type="RESPONSE",
            message="I opened calculator.",
            tool=None,
            action=None,
        )

        tasks = agent.run("What did you just do?")
        agent.close()

        assert len(tasks) == 1
        resp_task = tasks[0]
        # Must be rejected because no tool ran!
        assert "No actions were executed" in resp_task.result
        assert "without executing the required tool" in resp_task.result

    def test_9b_ordinary_conversation_is_not_rejected(self):
        """9b. Ordinary conversational responses with 0 tools pass through untouched."""
        tool = FakeTool(name="windows")
        agent, _ = _build_test_agent(tool)

        agent._cognitive_manager.process_fast.return_value = ConversationResponse(
            type="RESPONSE",
            message="Hello! I can help you with tasks and information.",
        )

        tasks = agent.run("Hello there")
        agent.close()

        assert len(tasks) == 1
        assert tasks[0].result == "Hello! I can help you with tasks and information."

    def test_10_timeout_failure_is_correctly_represented(self):
        """10. When a tool exceeds its configured timeout, it safely fails with timeout error."""
        tool = FakeTool(name="windows")
        # Set agent default timeout to 0.1s
        agent, executor = _build_test_agent(tool, default_timeout=0.1)

        agent._cognitive_manager.process_fast.return_value = ConversationResponse(
            type="ACTION",
            message="Executing slow action.",
            tool="windows",
            action="slow_action",
            parameters={},
        )

        tasks = agent.run("Do slow task")
        agent.close()

        assert len(tasks) == 2
        tool_task = tasks[1]
        assert tool_task.status == TaskStatus.FAILED
        assert "timed out after" in tool_task.error

        # Result grounding reflects timeout
        resp_task = tasks[0]
        assert "timed out after" in resp_task.result

    def test_end_to_end_build_agent_has_execution_policy(self):
        """Verify that main.build_agent() constructs an Agent with active ExecutionPolicy."""
        jarvis_bundle = build_agent()
        agent = jarvis_bundle["agent"]
        policy = jarvis_bundle["execution_policy"]

        assert agent.execution_policy is not None
        assert agent.execution_policy is policy
        assert isinstance(agent.execution_policy, ExecutionPolicy)
        agent.close()
