"""
Regression tests for Phase 3 (system.respond Handling) and Phase 4 (Task Retry State Hardening).

Phase 3 Tests:
1. response only
2. tool + response (tool executed first, response processed after)
3. malformed response (int/dict/empty message handled gracefully)
4. response attempting to contain an executable action (never executed)
5. response after tool failure
6. response under mission execution

Phase 4 Tests:
1. normal task success
2. normal task failure
3. one retry after failure
4. retry limit reached
5. repeated identical tool failure
6. successful recovery after failure
7. failed -> retry -> running
8. retry after validation failure
9. retry after executor failure
10. retry cannot bypass security policy
"""

from unittest.mock import MagicMock
import pytest

from core.agent import Agent
from core.cognition.conversation import ConversationEngine, ConversationResponse
from core.exceptions import InvalidStateError, JarvisError
from core.execution_policy import (
    ExecutionPolicy,
    PolicyContext,
    CapabilitySource,
    PolicyVerdict,
)
from core.registry import Registry
from core.task import Task, TaskStatus
from core.validator import Validator
from tools.base_tool import BaseTool


# ---------------------------------------------------------------------------
# Mocks & Helpers
# ---------------------------------------------------------------------------

class DummyEchoTool(BaseTool):
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "Dummy echo tool for testing"

    def get_actions(self):
        from core.action_definition import ActionDefinition
        return {
            "echo": ActionDefinition(name="echo", description="echo", required_args=["msg"]),
            "fail_action": ActionDefinition(name="fail_action", description="fails", required_args=["msg"]),
        }

    def execute(self, action: str, args: dict) -> str:
        if action == "fail_action":
            from core.exceptions import ExecutionError
            raise ExecutionError("Deliberate tool failure")
        return f"ECHO: {args.get('msg', '')}"


# ===========================================================================
# Phase 3 Tests — system.respond Handling
# ===========================================================================

class TestSystemRespondHandling:
    """Test suite for system.respond pseudo-tool handling."""

    def test_1_response_only(self):
        """1. Plain conversational response completes cleanly without external tool dispatch."""
        planner = MagicMock()
        validator = MagicMock()
        executor = MagicMock()
        cognitive = MagicMock()
        cognitive.process_fast.return_value = ConversationResponse(
            type="RESPONSE",
            message="Good day, human!",
        )

        agent = Agent(planner, validator, executor, cognitive_manager=cognitive)
        tasks = agent.run("Hello there")

        assert len(tasks) == 1
        assert tasks[0].tool == "system"
        assert tasks[0].action == "respond"
        assert tasks[0].status == TaskStatus.COMPLETED
        assert tasks[0].result == "Good day, human!"
        executor.execute.assert_not_called()

    def test_2_tool_plus_response_order(self):
        """2. When tool + response are present, tool executes FIRST, then response processes."""
        planner = MagicMock()
        validator = MagicMock()
        executor = MagicMock()

        execution_order = []

        def mock_validate(t):
            return t

        validator.validate.side_effect = mock_validate

        def mock_execute(t):
            execution_order.append(f"{t.tool}.{t.action}")
            t.start()
            t.complete("tool done")
            return t

        executor.execute.side_effect = mock_execute

        cognitive = MagicMock()
        # Returns an ACTION response (which creates system.respond + tool action)
        cognitive.process_fast.return_value = ConversationResponse(
            type="ACTION",
            message="I will create the file.",
            tool="file",
            action="create_file",
            parameters={"path": "demo.txt"},
        )

        agent = Agent(planner, validator, executor, cognitive_manager=cognitive)
        tasks = agent.run("create demo.txt")

        # The tool MUST have been sent to executor
        assert "file.create_file" in execution_order
        # Both tasks completed
        assert all(t.status == TaskStatus.COMPLETED for t in tasks)
        # Verify system.respond was NOT sent to executor
        assert "system.respond" not in execution_order

    def test_3_malformed_response_handled_gracefully(self):
        """3. Malformed fields (int, dict, list, None) in system.respond args don't crash the agent."""
        planner = MagicMock()
        validator = MagicMock()
        executor = MagicMock()

        agent = Agent(planner, validator, executor)

        # Non-string message
        t1 = Task(tool="system", action="respond", args={"message": 12345})
        res1 = agent._process_task(t1)
        assert res1.status == TaskStatus.COMPLETED
        assert res1.result == "12345"

        # Content key fallback with nested dict
        t2 = Task(tool="system", action="respond", args={"content": {"status": "ok"}})
        res2 = agent._process_task(t2)
        assert res2.status == TaskStatus.COMPLETED
        assert "{'status': 'ok'}" in res2.result

        # Empty args
        t3 = Task(tool="system", action="respond", args={})
        res3 = agent._process_task(t3)
        assert res3.status == TaskStatus.COMPLETED
        assert res3.result == ""

    def test_4_response_attempting_executable_action_denied(self):
        """4. Hostile executable keys in system.respond are never executed."""
        planner = MagicMock()
        validator = MagicMock()
        executor = MagicMock()

        agent = Agent(planner, validator, executor)

        malicious_task = Task(
            tool="system",
            action="respond",
            args={
                "message": "Harmless message",
                "command": "format C:",
                "shell": "powershell -c evil",
                "action": "delete_file",
            },
        )
        res = agent._process_task(malicious_task)
        assert res.status == TaskStatus.COMPLETED
        assert res.result == "Harmless message"
        executor.execute.assert_not_called()

    def test_5_response_after_tool_failure(self):
        """5. When a tool fails, subsequent system.respond processes gracefully."""
        planner = MagicMock()
        validator = MagicMock()
        executor = MagicMock()

        failed_task = Task(tool="file", action="read_file", args={"path": "missing.txt"})
        resp_task = Task(tool="system", action="respond", args={"message": "Could not find file."})

        def mock_execute(t):
            t.start()
            t.fail("File not found")
            return t

        executor.execute.side_effect = mock_execute

        agent = Agent(planner, validator, executor)
        r1 = agent._process_task(failed_task)
        r2 = agent._process_task(resp_task)

        assert r1.status == TaskStatus.FAILED
        assert r2.status == TaskStatus.COMPLETED
        assert r2.result == "Could not find file."

    def test_6_response_under_mission_execution(self):
        """6. Mission response returned as system.respond conclusion."""
        planner = MagicMock()
        validator = MagicMock()
        executor = MagicMock()
        cap_manager = MagicMock()

        # Capability manager routes with simple response
        mock_plan = MagicMock(required_capabilities=[], requires_memory=False, requires_knowledge=False)
        mock_plan.requires_animation = False
        mock_plan.requires_voice = False
        mock_plan.requires_video = False
        mock_plan.requires_music = False
        mock_plan.requires_subtitles = False
        mock_plan.requires_thumbnail = False
        mock_plan.requires_seo = False
        mock_plan.requires_publishing = False
        mock_plan.requires_analytics = False
        cap_manager.route.return_value = (mock_plan, MagicMock(name="profile"))

        planner.plan.return_value = [Task(tool="system", action="respond", args={"message": "Mission completed."})]
        agent = Agent(planner, validator, executor, capability_manager=cap_manager)
        tasks = agent._handle_mission("Test mission", "")
        assert isinstance(tasks, list)
        assert len(tasks) == 1
        assert tasks[0].tool == "system"
        assert tasks[0].action == "respond"


# ===========================================================================
# Phase 4 Tests — Task Retry State Hardening
# ===========================================================================

class TestTaskRetryStateMachine:
    """Test suite for controlled Task retry lifecycle and state machine."""

    def test_1_normal_task_success(self):
        """1. PENDING -> RUNNING -> COMPLETED."""
        task = Task(tool="dummy", action="echo", args={"msg": "hi"})
        assert task.status == TaskStatus.PENDING

        task.start()
        assert task.status == TaskStatus.RUNNING

        task.complete("done")
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "done"
        assert task.is_terminal is True

    def test_2_normal_task_failure(self):
        """2. PENDING -> RUNNING -> FAILED."""
        task = Task(tool="dummy", action="echo", args={"msg": "hi"})
        task.start()
        task.fail("timeout")
        assert task.status == TaskStatus.FAILED
        assert task.error == "timeout"
        assert task.is_terminal is True

    def test_3_one_retry_after_failure(self):
        """3. FAILED -> RETRYING -> RUNNING -> COMPLETED."""
        task = Task(tool="dummy", action="echo", args={"msg": "hi"})
        task.start()
        task.fail("transient error")
        assert task.status == TaskStatus.FAILED

        # Controlled retry
        task.retry()
        assert task.status == TaskStatus.RETRYING
        assert task.retry_count == 1
        assert task.failure_history == ["transient error"]
        assert task.error == ""
        assert task.is_terminal is False

        # Resume execution
        task.start()
        assert task.status == TaskStatus.RUNNING
        task.complete("success on retry")
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "success on retry"
        assert task.failure_history == ["transient error"]

    def test_4_retry_limit_reached(self):
        """4. Retrying beyond max_retries raises InvalidStateError."""
        task = Task(tool="dummy", action="echo", max_retries=2)
        task.start()
        task.fail("err 1")

        # Retry 1
        task.retry()
        task.start()
        task.fail("err 2")

        # Retry 2
        task.retry()
        task.start()
        task.fail("err 3")

        # Attempting Retry 3 (exceeds max_retries=2)
        assert task.retry_count == 2
        with pytest.raises(InvalidStateError) as exc:
            task.retry()
        assert "retry limit reached" in str(exc.value)

    def test_5_repeated_identical_tool_failure(self):
        """5. Repeated identical tool failures accumulate in failure_history."""
        task = Task(tool="dummy", action="echo", max_retries=3)
        for i in range(3):
            if task.status == TaskStatus.PENDING:
                task.start()
            else:
                task.retry()
                task.start()
            task.fail(f"Failure attempt {i+1}")

        assert task.retry_count == 2
        assert len(task.failure_history) == 2
        assert task.error == "Failure attempt 3"

    def test_6_successful_recovery_after_failure(self):
        """6. Task recovers and completes after initial failure."""
        task = Task(tool="dummy", action="echo")
        task.start()
        task.fail("Connection reset")

        task.retry()
        task.start()
        task.complete("Connected")

        assert task.status == TaskStatus.COMPLETED
        assert task.retry_count == 1
        assert task.result == "Connected"

    def test_7_failed_to_retry_to_running_transition(self):
        """7. Cannot transition directly from FAILED to RUNNING without retry()."""
        task = Task(tool="dummy", action="echo")
        task.start()
        task.fail("fatal")

        # Calling start() directly from FAILED is illegal
        with pytest.raises(InvalidStateError) as exc:
            task.start()
        assert "Cannot transition from failed to running" in str(exc.value)

        # Must go FAILED -> RETRYING -> RUNNING
        task.retry()
        assert task.status == TaskStatus.RETRYING
        task.start()
        assert task.status == TaskStatus.RUNNING

    def test_8_retry_after_validation_failure(self):
        """8. Task failing validation can be retried and validated again."""
        registry = Registry()
        tool = DummyEchoTool()
        registry.register(tool)
        validator = Validator(registry)

        # Missing required argument 'msg'
        task = Task(tool="dummy", action="echo", args={})
        with pytest.raises(JarvisError):
            validator.validate(task)

        task.start()
        task.fail("Validation failed: Missing required argument 'msg'")

        # Retry with fixed arguments
        task.retry()
        task.args["msg"] = "fixed"
        validator.validate(task)
        task.start()
        result = tool.execute(task.action, task.args)
        task.complete(result)

        assert task.status == TaskStatus.COMPLETED
        assert task.result == "ECHO: fixed"

    def test_9_retry_after_executor_failure(self):
        """9. Executor failure can be retried cleanly through Agent._process_task."""
        planner = MagicMock()
        validator = MagicMock()
        executor = MagicMock()

        calls = 0

        def mock_execute(t):
            nonlocal calls
            calls += 1
            if getattr(t, "status", None) in (TaskStatus.PENDING, TaskStatus.RETRYING):
                t.start()
            if calls == 1:
                t.fail("I/O error")
            else:
                t.complete("recovered data")
            return t

        executor.execute.side_effect = mock_execute
        validator.validate.side_effect = lambda t: t

        agent = Agent(planner, validator, executor)
        task = Task(tool="file", action="read_file", args={"path": "data.txt"})

        r1 = agent._process_task(task)
        assert r1.status == TaskStatus.FAILED
        assert calls == 1

        # Controlled retry
        task.retry()
        r2 = agent._process_task(task)
        assert r2.status == TaskStatus.COMPLETED
        assert r2.result == "recovered data"
        assert calls == 2

    def test_10_retry_cannot_bypass_security_policy(self):
        """10. Retried tasks must still pass through ExecutionPolicy check."""
        policy = ExecutionPolicy()
        high_risk_ctx = PolicyContext(
            tool="windows",
            action="shutdown",
            source=CapabilitySource.CORE,
        )

        # Attempt 1: blocked
        decision1 = policy.check(high_risk_ctx)
        assert decision1.verdict == PolicyVerdict.DENY

        # Retrying does not grant privilege
        task = Task(tool="windows", action="shutdown", args={})
        task.start()
        task.fail(decision1.reason)

        task.retry()
        decision2 = policy.check(high_risk_ctx)
        assert decision2.verdict == PolicyVerdict.DENY
        assert "denied" in decision2.reason.lower()
