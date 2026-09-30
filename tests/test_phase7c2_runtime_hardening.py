"""
JARVIS Phase 7C.2 — Runtime Spine Hardening Integration Tests.

Validates the fixes for:
  - P1.1: Zero-tool mission false pass prevention
  - P1.2: Retry history and successful recovery with effective state
  - P2.1: CHAT -> PLAN escalation to effective MISSION
  - P2.2: Content Factory external side effects policy gate
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from core.agent import Agent
from core.cognition.conversation import ConversationResponse
from core.execution_policy import (
    CapabilitySource,
    ExecutionPolicy,
    PolicyContext,
    PolicyResult,
    PolicyVerdict,
)
from core.execution_summary import ExecutionSummary
from core.mission_verifier import (
    FileExistsCheck,
    MissionCompletionVerifier,
    MissionPostcondition,
    ToolSucceededCheck,
    VerificationResult,
    VerificationStatus,
    get_effective_tasks,
)
from core.routing.intent_classifier import IntentType
from core.task import Task, TaskStatus


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------

class DummyPlanner:
    def __init__(self, tasks: list[Task] | None = None) -> None:
        self._tasks = tasks or []

    def plan(self, user_input: str, context: str = "") -> list[Task]:
        return [
            Task(
                tool=t.tool,
                action=t.action,
                args=dict(t.args),
                timeout_seconds=getattr(t, "timeout_seconds", None),
                source=getattr(t, "source", None),
            )
            for t in self._tasks
        ]


class DummyValidator:
    def validate(self, task: Task) -> None:
        pass


class DummyExecutor:
    def __init__(self, side_effects: dict[str, Any] | None = None) -> None:
        self.side_effects = side_effects or {}
        self.executed: list[Task] = []

    def execute(self, task: Task) -> Task:
        self.executed.append(task)
        if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
            task.start()

        key = f"{task.tool}.{task.action}"
        if key in self.side_effects:
            eff = self.side_effects[key]
            if isinstance(eff, Exception):
                task.fail(str(eff))
            elif callable(eff):
                res = eff(task)
                if isinstance(res, tuple) and len(res) == 2 and not res[0]:
                    task.fail(res[1])
                else:
                    task.complete(res)
            else:
                task.complete(eff)
        else:
            task.complete(f"Executed {task.tool}.{task.action}")
        return task


def _build_test_agent(
    planned_tasks: list[Task] | None = None,
    side_effects: dict[str, Any] | None = None,
    execution_policy: ExecutionPolicy | None = None,
    cognitive_manager: Any = None,
    capability_manager: Any = None,
    n8n_manager: Any = None,
    script_engine: Any = None,
) -> tuple[Agent, DummyExecutor]:
    planner = DummyPlanner(planned_tasks or [])
    validator = DummyValidator()
    executor = DummyExecutor(side_effects or {})
    policy = execution_policy or ExecutionPolicy(allow_destructive_from_core=True)
    verifier = MissionCompletionVerifier()

    agent = Agent(
        planner=planner,
        validator=validator,
        executor=executor,
        execution_policy=policy,
        mission_verifier=verifier,
        cognitive_manager=cognitive_manager,
        capability_manager=capability_manager,
        n8n_manager=n8n_manager,
        script_engine=script_engine,
    )
    return agent, executor


# ===========================================================================
# P1.1: ZERO-TOOL MISSION FALSE PASS TESTS
# ===========================================================================

class TestZeroToolMissionFalsePass:
    """Validate that missions with 0 tools cannot falsely pass merely because response exists."""

    def test_zero_tool_mission_plus_response_fails_verification(self):
        """Zero-tool mission + long response produces FAILED (NOT_VERIFIED), not PASSED."""
        verifier = MissionCompletionVerifier()
        # Only system respond task
        tasks = [Task(tool="system", action="respond", args={"message": "I completed your research request thoroughly."})]
        res = verifier.verify(tasks=tasks, response_text="I completed your research request thoroughly.")

        assert res.status == VerificationStatus.FAILED
        assert res.is_not_verified
        assert not res.succeeded
        assert any("FAIL [MissionEvidence]" in d for d in res.details)

    def test_zero_tool_mission_plus_done_claim_grounded_as_failure(self):
        """Model says 'Done.' with 0 tools executed in mission -> grounded as failure."""
        agent, _ = _build_test_agent(planned_tasks=[])
        # User input classified as MISSION
        results = agent.run("Plan and execute: analyze the stock market", intent=IntentType.MISSION)

        resp = next(t for t in results if t.tool == "system" and t.action == "respond")
        assert agent.last_verification_result is not None
        assert agent.last_verification_result.status == VerificationStatus.FAILED
        assert "mission verification failed" in str(resp.result).lower()
        assert agent.last_mission_telemetry["verification_status"] == "failed"

    def test_zero_tool_mission_plus_empty_response_fails(self):
        """Zero-tool mission + empty response produces FAILED."""
        verifier = MissionCompletionVerifier()
        tasks = [Task(tool="system", action="respond", args={"message": ""})]
        res = verifier.verify(tasks=tasks, response_text="")

        assert res.status == VerificationStatus.FAILED
        assert res.is_not_verified

    def test_normal_chat_zero_tools_remains_unaffected(self):
        """Normal CHAT with 0 tools executes cleanly and verifier is completely bypassed."""
        cog = MagicMock()
        cog.process_fast.return_value = ConversationResponse(type="RESPONSE", message="Hello! I am Jarvis.")

        agent, _ = _build_test_agent(cognitive_manager=cog)
        results = agent.run("Hello there", intent=IntentType.CHAT)

        resp = next(t for t in results if t.tool == "system" and t.action == "respond")
        assert resp.result == "Hello! I am Jarvis."
        assert agent.last_verification_result is None
        assert agent.last_mission_telemetry is None


# ===========================================================================
# P1.2: RETRY HISTORY AND SUCCESSFUL RECOVERY TESTS
# ===========================================================================

class TestRetryHistoryAndEffectiveState:
    """Validate that attempt history is preserved while effective state governs verification."""

    def test_fail_then_retry_success_verified_complete(self):
        """Iteration 1 fail, iteration 2 success on same task -> VERIFIED_COMPLETE."""
        t1 = Task(tool="file", action="read_file", args={"path": "data.txt"})
        t1.start()
        t1.fail("Temporary I/O error")

        t2 = Task(tool="file", action="read_file", args={"path": "data.txt"})
        t2.start()
        t2.complete("File content loaded")

        verifier = MissionCompletionVerifier()
        # Pass full history of both attempts
        res = verifier.verify(tasks=[t1, t2], response_text="Loaded file data.")

        assert res.status == VerificationStatus.PASSED
        assert res.is_verified_complete
        assert any("recovered after retry" in d for d in res.details)

    def test_fail_then_retry_fail_not_verified(self):
        """Iteration 1 fail, iteration 2 fail on same task -> NOT_VERIFIED (FAILED)."""
        t1 = Task(tool="file", action="read_file", args={"path": "data.txt"})
        t1.start()
        t1.fail("Not found attempt 1")

        t2 = Task(tool="file", action="read_file", args={"path": "data.txt"})
        t2.start()
        t2.fail("Not found attempt 2")

        verifier = MissionCompletionVerifier()
        res = verifier.verify(tasks=[t1, t2], response_text="Could not read file.")

        assert res.status == VerificationStatus.FAILED
        assert res.is_not_verified

    def test_task_a_success_and_task_b_failure_partial(self):
        """Distinct tasks A (success) and B (failure) -> PARTIAL."""
        ta = Task(tool="file", action="create_file", args={"path": "a.txt"})
        ta.start()
        ta.complete("Created a.txt")

        tb = Task(tool="file", action="read_file", args={"path": "b.txt"})
        tb.start()
        tb.fail("b.txt missing")

        verifier = MissionCompletionVerifier()
        res = verifier.verify(tasks=[ta, tb], response_text="Created a but could not read b.")

        assert res.status == VerificationStatus.PARTIAL
        assert res.is_partial
        assert not res.is_verified_complete

    def test_three_repeated_failures_bounded_termination(self):
        """Three attempts of same task failing -> effective state is FAILED, not PASSED."""
        attempts = []
        for i in range(1, 4):
            t = Task(tool="windows", action="open_app", args={"app": "notepad"})
            t.start()
            t.fail(f"Failure attempt {i}")
            attempts.append(t)

        effective = get_effective_tasks(attempts)
        assert len(effective) == 1
        assert effective[0].status == TaskStatus.FAILED

        verifier = MissionCompletionVerifier()
        res = verifier.verify(tasks=attempts, response_text="Failed after 3 attempts.")
        assert res.status == VerificationStatus.FAILED

    def test_telemetry_retains_all_attempts_and_effective_state(self):
        """Telemetry preserves all executed attempts and records effective task state."""
        t1 = Task(tool="file", action="read_file", args={"path": "config.json"})
        t1.start()
        t1.fail("File locked")

        t2 = Task(tool="file", action="read_file", args={"path": "config.json"})
        t2.start()
        t2.complete('{"key": "value"}')

        summary = ExecutionSummary.from_tasks([t1, t2])
        assert summary.total_attempts == 2
        assert len(summary.attempt_history) == 2
        assert summary.total_tasks == 1
        assert summary.all_succeeded is True
        assert summary.all_failed is False
        assert summary.is_partial is False

    def test_verifier_evaluates_effective_final_state(self):
        """get_effective_tasks correctly collapses retries across backslashes and case."""
        t1 = Task(tool="file", action="read_file", args={"path": "C:\\Data\\test.txt"})
        t1.start()
        t1.fail("I/O error")

        t2 = Task(tool="file", action="read_file", args={"path": "c:/data/test.txt"})
        t2.start()
        t2.complete("Success")

        effective = get_effective_tasks([t1, t2])
        assert len(effective) == 1
        assert effective[0].status == TaskStatus.COMPLETED


# ===========================================================================
# P2.1: CHAT -> PLAN ESCALATION TESTS
# ===========================================================================

class TestChatToPlanEscalation:
    """Validate that conversational escalation to PLAN acquires effective MISSION semantics."""

    def test_chat_remains_chat_when_no_escalation(self):
        """CHAT returning RESPONSE stays CHAT, verifier bypassed."""
        cog = MagicMock()
        cog.process_fast.return_value = ConversationResponse(type="RESPONSE", message="This is a simple answer.")

        agent, _ = _build_test_agent(cognitive_manager=cog)
        agent.run("What is photosynthesis?", intent=IntentType.CHAT)

        assert agent.last_verification_result is None
        assert agent.last_mission_telemetry is None

    def test_chat_to_plan_becomes_effective_mission(self):
        """CHAT returning PLAN escalates to MISSION and executes verifier."""
        cog = MagicMock()
        cog.process_fast.return_value = ConversationResponse(type="PLAN", message="I have created a multi-step plan.")

        tool_task = Task(tool="file", action="create_file", args={"path": "report.txt"})
        agent, _ = _build_test_agent(planned_tasks=[tool_task], cognitive_manager=cog)

        agent.run("Can you build a report on this?", intent=IntentType.CHAT)

        # Must have escalated to MISSION and executed verifier
        assert agent.last_verification_result is not None
        assert agent.last_mission_telemetry is not None
        assert agent.last_mission_telemetry["mission_detected"] is True

    def test_escalated_mission_reaches_verifier(self, tmp_path: Path):
        """Escalated mission runs verifier and grounds final response."""
        target = tmp_path / "output.txt"
        cog = MagicMock()
        cog.process_fast.return_value = ConversationResponse(type="PLAN", message="Executing plan.")

        def _create(t: Task) -> str:
            target.write_text("EXPORTED_DATA", encoding="utf-8")
            return f"Created {target}"

        tool_task = Task(tool="file", action="create_file", args={"path": str(target)})
        agent, _ = _build_test_agent(
            planned_tasks=[tool_task],
            side_effects={"file.create_file": _create},
            cognitive_manager=cog,
        )

        results = agent.run("Please organize and export my data", intent=IntentType.CHAT)
        resp = next(t for t in results if t.tool == "system" and t.action == "respond")

        assert agent.last_verification_result is not None
        assert agent.last_verification_result.status == VerificationStatus.PASSED
        assert "created file:" in str(resp.result)
        assert str(target) in str(resp.result)

    def test_ordinary_chat_still_bypasses_verifier(self):
        """Ordinary chat greetings or answers strictly bypass verifier."""
        cog = MagicMock()
        cog.process_fast.return_value = ConversationResponse(type="RESPONSE", message="Good morning!")

        agent, _ = _build_test_agent(cognitive_manager=cog)
        agent.run("Good morning Jarvis", intent=IntentType.CHAT)

        assert agent.last_verification_result is None


# ===========================================================================
# P2.2: CONTENT FACTORY POLICY GATE TESTS
# ===========================================================================

class TestContentFactoryExecutionPolicyGate:
    """Validate that Content Factory external side effects pass through ExecutionPolicy."""

    def test_publishing_engine_requires_confirmation_or_allow(self):
        """Publishing engine side effect is checked against ExecutionPolicy (requires confirmation)."""
        cap_mgr = MagicMock()
        plan = MagicMock()
        plan.requires_memory = False
        plan.requires_knowledge = False
        plan.requires_automation = False
        plan.requires_scripting = False
        plan.requires_storyboard = False
        plan.requires_project_management = False
        plan.requires_image_generation = False
        plan.requires_animation = False
        plan.requires_voice = False
        plan.requires_video = False
        plan.requires_music = False
        plan.requires_subtitles = False
        plan.requires_thumbnail = False
        plan.requires_seo = False
        plan.requires_publishing = True
        plan.requires_analytics = False
        plan.requires_planner = False
        plan.metadata = {"project_id": "proj_123", "platforms": ["youtube"]}

        cap_mgr.route.return_value = (plan, MagicMock(name="qwen3:8b"))

        policy = ExecutionPolicy(allow_destructive_from_core=True)
        agent, _ = _build_test_agent(
            execution_policy=policy,
            capability_manager=cap_mgr,
        )

        # Without user confirmation: high-risk action "publish" requires confirmation
        tasks = agent._handle_mission("Publish this video to YouTube", "", user_confirmed=False)
        assert len(tasks) == 1
        assert tasks[0].status == TaskStatus.FAILED
        assert "requires user confirmation" in str(tasks[0].error).lower()

    def test_publishing_engine_allowed_with_user_confirmed(self):
        """Publishing engine side effect executes when user_confirmed=True."""
        cap_mgr = MagicMock()
        plan = MagicMock()
        plan.requires_memory = False
        plan.requires_knowledge = False
        plan.requires_automation = False
        plan.requires_scripting = False
        plan.requires_storyboard = False
        plan.requires_project_management = False
        plan.requires_image_generation = False
        plan.requires_animation = False
        plan.requires_voice = False
        plan.requires_video = False
        plan.requires_music = False
        plan.requires_subtitles = False
        plan.requires_thumbnail = False
        plan.requires_seo = False
        plan.requires_publishing = True
        plan.requires_analytics = False
        plan.requires_planner = False
        plan.metadata = {"project_id": "proj_123", "platforms": ["youtube"]}

        pub_mgr = MagicMock()
        pub_mgr.publish_async.return_value = "mission_pub_999"
        cap_mgr.route.return_value = (plan, MagicMock(name="qwen3:8b"))
        cap_mgr.get_handler.return_value = pub_mgr

        policy = ExecutionPolicy(allow_destructive_from_core=True)
        agent, _ = _build_test_agent(
            execution_policy=policy,
            capability_manager=cap_mgr,
        )

        tasks = agent._handle_mission("Publish this video to YouTube", "", user_confirmed=True)
        assert len(tasks) == 1
        assert "mission_pub_999" in tasks[0].args["message"]

    def test_automation_engine_requires_confirmation(self):
        """Automation workflow trigger checks ExecutionPolicy."""
        cap_mgr = MagicMock()
        plan = MagicMock()
        plan.requires_memory = False
        plan.requires_knowledge = False
        plan.requires_automation = True
        plan.requires_scripting = False
        plan.requires_storyboard = False
        plan.requires_project_management = False
        plan.requires_image_generation = False
        plan.requires_animation = False
        plan.requires_voice = False
        plan.requires_video = False
        plan.requires_music = False
        plan.requires_subtitles = False
        plan.requires_thumbnail = False
        plan.requires_seo = False
        plan.requires_publishing = False
        plan.requires_analytics = False
        plan.requires_planner = False

        cap_mgr.route.return_value = (plan, MagicMock(name="qwen3:8b"))

        n8n_mgr = MagicMock()
        n8n_mgr.list_workflows.return_value = ["sync_data"]
        n8n_mgr.execute_workflow_by_name.return_value = "n8n_mission_123"

        policy = ExecutionPolicy(allow_destructive_from_core=True)
        agent, _ = _build_test_agent(
            execution_policy=policy,
            capability_manager=cap_mgr,
            n8n_manager=n8n_mgr,
        )

        tasks = agent._handle_mission("Run sync automation workflow", "", user_confirmed=False)
        assert len(tasks) == 1
        assert tasks[0].status == TaskStatus.FAILED
        assert "requires user confirmation" in str(tasks[0].error).lower()

    def test_pure_generation_remains_lightweight_without_policy_blocking(self):
        """Script engine (pure content generation) executes directly without policy denial."""
        cap_mgr = MagicMock()
        plan = MagicMock()
        plan.requires_memory = False
        plan.requires_knowledge = False
        plan.requires_automation = False
        plan.requires_scripting = True
        plan.requires_storyboard = False
        plan.requires_project_management = False
        plan.requires_image_generation = False
        plan.requires_animation = False
        plan.requires_voice = False
        plan.requires_video = False
        plan.requires_music = False
        plan.requires_subtitles = False
        plan.requires_thumbnail = False
        plan.requires_seo = False
        plan.requires_publishing = False
        plan.requires_analytics = False
        plan.requires_planner = False
        plan.style = "documentary"

        script_mgr = MagicMock()
        script_mgr.generate_script_async.return_value = "script_mission_456"
        cap_mgr.route.return_value = (plan, MagicMock(name="qwen3:8b"))

        policy = ExecutionPolicy(allow_destructive_from_core=True)
        agent, _ = _build_test_agent(
            execution_policy=policy,
            capability_manager=cap_mgr,
            script_engine=script_mgr,
        )

        # Executes without user confirmation because pure generation has no external side effects
        tasks = agent._handle_mission("Write a documentary script about Mars", "", user_confirmed=False)
        assert len(tasks) == 1
        assert "script_mission_456" in tasks[0].args["message"]
