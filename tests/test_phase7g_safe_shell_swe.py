"""
JARVIS Phase 7G — Safe Shell & Software Engineering Execution Tests.

Verifies the 25 production-path requirements:
1. shell tool registration
2. safe command execution
3. workspace restriction
4. outside-workspace path denial
5. command chaining denial
6. PowerShell injection denial
7. environment secret stripping
8. shell timeout
9. stdout capture
10. stderr capture
11. shell output marked untrusted
12. oversized shell output bounded by ContextBudget
13. model cannot self-authorize shell
14. high-risk shell action requires confirmation
15. file edit remains workspace bounded
16. failed test result returns to model
17. model can react to test failure
18. model can rerun tests
19. successful test run reaches verification
20. failed SWE mission is not reported as complete
21. CHAT does not invoke shell
22. MEMORY does not invoke shell
23. session continuity works for SWE follow-up
24. request trace records shell events
25. policy decision recorded for shell execution
"""

import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.agent import Agent
from core.cognition.context import ShortTermContext
from core.cognition.conversation import ConversationResponse
from core.context_budget import ContextBudget, ContextBudgetManager
from core.execution_policy import CapabilitySource, ExecutionPolicy, PolicyContext, PolicyVerdict
from core.mission_verifier import MissionCompletionVerifier, VerificationStatus
from core.registry import Registry
from core.routing.intent_classifier import IntentType
from core.session import SessionRepository
from core.task import Task, TaskStatus
from core.tool_feedback_loop import ToolFeedbackLoop, format_untrusted_tool_result
from tools.file import FileTool
from tools.shell import ShellTool


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


class MockSWEProvider:
    """Mock LLM provider returning simulated SWE model actions."""

    def __init__(self, responses: list[dict] | None = None) -> None:
        self._responses = list(responses or [])
        self.call_history: list[dict] = []

    def generate(self, system_prompt: str, user_prompt: str, requirements=None):
        self.call_history.append({"system": system_prompt, "user": user_prompt})
        if self._responses:
            data = self._responses.pop(0)
        else:
            data = {"type": "RESPONSE", "message": "Done."}

        import json
        mock_resp = MagicMock()
        mock_resp.text = json.dumps(data)
        mock_resp.token_usage = {"prompt_tokens": 15, "completion_tokens": 10}
        return mock_resp


def build_swe_test_agent(
    workspace_path: Path,
    provider: MockSWEProvider | None = None,
    allow_destructive: bool = True,
) -> tuple[Agent, ShellTool, FileTool, MockSWEProvider]:
    """Construct a production-structured Agent wired for Shell and SWE."""
    prov = provider or MockSWEProvider()
    shell_tool = ShellTool(workspace_root=workspace_path, timeout_seconds=5.0)
    file_tool = FileTool()

    registry = Registry()
    registry.register(shell_tool)
    registry.register(file_tool)

    # Context & cognitive mock
    st_ctx = ShortTermContext(max_history=10)
    cog_manager = MagicMock()
    cog_manager._context = st_ctx

    def _proc_fast(msg, intent="chat"):
        res = prov.generate("", msg)
        import json
        try:
            data = json.loads(res.text)
        except Exception:
            data = {"type": "RESPONSE", "message": res.text}
        resp = ConversationResponse(
            type=data.get("type", "RESPONSE"),
            message=data.get("message", "Executed."),
            tool=data.get("tool"),
            action=data.get("action"),
            parameters=data.get("parameters", {}),
        )
        st_ctx.add_message("user", msg)
        st_ctx.add_message("assistant", resp.message)
        return resp

    cog_manager.process_fast.side_effect = _proc_fast
    cog_manager.last_context_budget = ContextBudget(user_input_tokens=10, history_tokens=20)

    # Policy
    policy = ExecutionPolicy(allow_destructive_from_core=allow_destructive)

    # Validator & verifier
    verifier = MissionCompletionVerifier()

    # Real Executor dispatching to registered tools
    executor = MagicMock()
    def _real_exec(t: Task) -> Task:
        if t.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
            t.start()
        try:
            if t.tool == "shell":
                out = shell_tool.execute(t.action, t.args)
                t.complete(out)
            elif t.tool == "file":
                out = file_tool.execute(t.action, t.args)
                t.complete(out)
            elif t.tool == "system":
                t.complete(str(t.args.get("message", "")))
            else:
                t.complete(f"Executed {t.tool}.{t.action}")
        except Exception as exc:
            t.fail(str(exc))
        return t

    executor.execute.side_effect = _real_exec

    agent = Agent(
        planner=MagicMock(),
        validator=MagicMock(),
        executor=executor,
        cognitive_manager=cog_manager,
        execution_policy=policy,
        mission_verifier=verifier,
        session_repository=SessionRepository(),
    )
    return agent, shell_tool, file_tool, prov


# ---------------------------------------------------------------------------
# Test Suite: Phase 7G Safe Shell & SWE Execution
# ---------------------------------------------------------------------------


class TestPhase7GSafeShellSWE:
    """Production-path test suite for Phase 7G Safe Shell & Software Engineering Execution."""

    # 1. shell tool registration
    def test_1_shell_tool_registration(self, tmp_path: Path):
        registry = Registry()
        tool = ShellTool(workspace_root=tmp_path)
        registry.register(tool)
        assert registry.get("shell") is tool
        assert "run" in tool.get_actions()
        assert "execute" in tool.get_actions()

    # 2. safe command execution
    def test_2_safe_command_execution(self, tmp_path: Path):
        tool = ShellTool(workspace_root=tmp_path)
        res = tool.run("echo safe_output")
        assert res.success
        assert "safe_output" in res.stdout
        assert res.return_code == 0

    # 3. workspace restriction
    def test_3_workspace_restriction(self, tmp_path: Path):
        tool = ShellTool(workspace_root=tmp_path)
        sub = tmp_path / "src"
        sub.mkdir()
        # Inside workspace allowed
        res1 = tool.run("echo inside", cwd_override=str(sub))
        assert not res1.blocked

        # Outside workspace blocked
        res2 = tool.run("echo outside", cwd_override=str(tmp_path.parent))
        assert res2.blocked
        assert "outside workspace" in res2.blocked_reason.lower()

    # 4. outside-workspace path denial
    def test_4_outside_workspace_path_denial(self, tmp_path: Path):
        tool = ShellTool(workspace_root=tmp_path)
        # Attempting path traversal
        res1 = tool.run("type ../outside.txt")
        assert res1.blocked
        assert "traversal" in res1.blocked_reason.lower() or "outside workspace" in res1.blocked_reason.lower()

        # Attempting absolute path outside workspace
        outside_path = "C:\\Windows\\System32\\drivers\\etc\\hosts"
        res2 = tool.run(f"type {outside_path}")
        assert res2.blocked
        assert "outside workspace" in res2.blocked_reason.lower()

    # 5. command chaining denial
    def test_5_command_chaining_denial(self, tmp_path: Path):
        tool = ShellTool(workspace_root=tmp_path)
        res = tool.run("echo hello | bash")
        assert res.blocked
        assert "high-risk" in res.blocked_reason.lower()

    # 6. PowerShell injection denial
    def test_6_powershell_injection_denial(self, tmp_path: Path):
        tool = ShellTool(workspace_root=tmp_path)
        res = tool.run("powershell -enc JABzACAAPQAgACIAZQ")
        assert res.blocked
        assert "high-risk" in res.blocked_reason.lower()

    # 7. environment secret stripping
    def test_7_environment_secret_stripping(self, tmp_path: Path):
        tool = ShellTool(workspace_root=tmp_path)
        os.environ["OPENAI_API_KEY"] = "sk-secret123"
        os.environ["JARVIS_SECRET_KEY"] = "super-secret"
        try:
            # Query environment from child process
            res = tool.run(f'{sys.executable} -c "import os; print(\'KEY:\', os.environ.get(\'OPENAI_API_KEY\', \'NOT_FOUND\'), os.environ.get(\'JARVIS_SECRET_KEY\', \'NOT_FOUND\'))"')
            assert res.success
            assert "KEY: NOT_FOUND NOT_FOUND" in res.stdout
            assert "sk-secret123" not in res.stdout
        finally:
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("JARVIS_SECRET_KEY", None)

    # 8. shell timeout
    def test_8_shell_timeout(self, tmp_path: Path):
        tool = ShellTool(workspace_root=tmp_path, timeout_seconds=0.2)
        res = tool.run(f'{sys.executable} -c "import time; time.sleep(3)"')
        assert res.timed_out
        assert not res.success

    # 9. stdout capture
    def test_9_stdout_capture(self, tmp_path: Path):
        tool = ShellTool(workspace_root=tmp_path)
        res = tool.run(f'{sys.executable} -c "print(\'CAPTURED_STDOUT_LINE\')"')
        assert res.success
        assert "CAPTURED_STDOUT_LINE" in res.stdout

    # 10. stderr capture
    def test_10_stderr_capture(self, tmp_path: Path):
        tool = ShellTool(workspace_root=tmp_path)
        res = tool.run(f'{sys.executable} -c "import sys; sys.stderr.write(\'CAPTURED_STDERR_ERROR\\n\')"')
        assert "CAPTURED_STDERR_ERROR" in res.stderr

    # 11. shell output marked untrusted
    def test_11_shell_output_marked_untrusted(self, tmp_path: Path):
        task = Task(tool="shell", action="run", args={"command": "pytest"})
        task.start()
        task.complete("3 passed in 0.42s")
        formatted = format_untrusted_tool_result(task)
        assert "<UNTRUSTED_TOOL_RESULT" in formatted
        assert "</UNTRUSTED_TOOL_RESULT>" in formatted
        assert "tool: shell.run" in formatted

    # 12. oversized shell output bounded by ContextBudget
    def test_12_oversized_shell_output_bounded_by_context_budget(self, tmp_path: Path):
        task = Task(tool="shell", action="run", args={"command": "pytest"})
        task.start()
        task.complete("x" * 20000)
        mgr = ContextBudgetManager(max_tool_result_chars=500)
        bounded = mgr.format_bounded_tool_result(task, max_chars=500)
        assert len(bounded) <= 1000
        assert "[truncated" in bounded
        assert "<UNTRUSTED_TOOL_RESULT>" in bounded

    # 13. model cannot self-authorize shell
    def test_13_model_cannot_self_authorize_shell(self, tmp_path: Path):
        policy = ExecutionPolicy()
        # Model claims user_confirmed in task args
        ctx = PolicyContext(
            tool="shell",
            action="run",
            user_confirmed=False,
            args={"command": "pip install evil-pkg", "user_confirmed": True},
        )
        res = policy.check(ctx)
        assert res.verdict in (PolicyVerdict.DENY, PolicyVerdict.REQUIRE_CONFIRMATION)
        assert res.verdict != PolicyVerdict.ALLOW

    # 14. high-risk shell action requires confirmation
    def test_14_high_risk_shell_action_requires_confirmation(self, tmp_path: Path):
        policy = ExecutionPolicy(allow_destructive_from_core=True)
        ctx = PolicyContext(
            tool="shell",
            action="run",
            user_confirmed=False,
            args={"command": "pip install requests"},
        )
        res = policy.check(ctx)
        assert res.verdict == PolicyVerdict.REQUIRE_CONFIRMATION

    # 15. file edit remains workspace bounded
    def test_15_file_edit_remains_workspace_bounded(self, tmp_path: Path):
        file_tool = FileTool()
        target = tmp_path / "hello.py"
        target.write_text("def run(): return 1\n", encoding="utf-8")

        # Edit inside workspace
        res = file_tool.execute("patch_file", {"path": str(target), "old_text": "return 1", "new_text": "return 42"})
        assert "Successfully modified" in res
        assert "return 42" in target.read_text(encoding="utf-8")

        # Attempting edit on protected path
        with pytest.raises(Exception, match="protected directory"):
            file_tool.execute("patch_file", {"path": "C:\\Windows\\notepad.exe", "old_text": "a", "new_text": "b"})

    # 16. failed test result returns to model
    def test_16_failed_test_result_returns_to_model(self, tmp_path: Path):
        prov = MockSWEProvider(responses=[
            {"type": "ACTION", "tool": "shell", "action": "run", "parameters": {"command": f"{sys.executable} -c \"raise ValueError('AssertionError in test')\""}},
            {"type": "RESPONSE", "message": "Observed test failure and diagnosing."},
        ])
        agent, _, _, _ = build_swe_test_agent(tmp_path, provider=prov)
        tasks = agent.run("Run tests", intent=IntentType.TOOL)
        assert any(t.tool == "shell" for t in tasks)
        assert len(prov.call_history) >= 1

    # 17. model can react to test failure
    def test_17_model_can_react_to_test_failure(self, tmp_path: Path):
        prov = MockSWEProvider(responses=[
            {"type": "ACTION", "tool": "shell", "action": "run", "parameters": {"command": f"{sys.executable} -c \"exit(1)\""}},
            {"type": "RESPONSE", "message": "Tests failed, attempting fix."},
        ])
        agent, _, _, _ = build_swe_test_agent(tmp_path, provider=prov)
        tasks = agent.run("Run pytest", intent=IntentType.TOOL)
        assert len(prov.call_history) >= 2
        second_call_prompt = prov.call_history[1]["user"]
        assert "<UNTRUSTED_TOOL_RESULT>" in second_call_prompt
        assert "return_code=1" in second_call_prompt or "exit(1)" in second_call_prompt

    # 18. model can rerun tests
    def test_18_model_can_rerun_tests(self, tmp_path: Path):
        tool = ShellTool(workspace_root=tmp_path)
        res1 = tool.run("echo run1")
        res2 = tool.run("echo run2")
        assert res1.success and res2.success
        assert "run1" in res1.stdout and "run2" in res2.stdout

    # 19. successful test run reaches verification
    def test_19_successful_test_run_reaches_verification(self, tmp_path: Path):
        test_file = tmp_path / "test_calc.py"
        test_file.write_text("def test_ok(): assert True\n", encoding="utf-8")

        verifier = MissionCompletionVerifier()
        # Simulated tasks with successful test command
        t_shell = Task(tool="shell", action="run", args={"command": "pytest test_calc.py"})
        t_shell.start()
        t_shell.complete("[return_code=0]\nSTDOUT:\n1 passed in 0.05s\nSTDERR:\n")

        t_resp = Task(tool="system", action="respond", args={"message": "All tests passed."})
        t_resp.start()
        t_resp.complete("All tests passed.")

        res = verifier.verify(
            tasks=[t_resp, t_shell],
            response_text="All tests passed.",
            user_input="Run pytest test_calc.py and verify all tests pass",
        )
        assert res.succeeded
        assert res.status == VerificationStatus.PASSED
        assert any("TestEvidence" in d for d in res.details)

    # 20. failed SWE mission is not reported as complete
    def test_20_failed_swe_mission_is_not_reported_as_complete(self, tmp_path: Path):
        verifier = MissionCompletionVerifier()
        # Simulated tasks where test failed
        t_shell = Task(tool="shell", action="run", args={"command": "pytest test_calc.py"})
        t_shell.start()
        t_shell.complete("[return_code=1]\nSTDOUT:\nFAILED test_calc.py::test_fail\nSTDERR:\n")

        t_resp = Task(tool="system", action="respond", args={"message": "I claim it is fixed."})
        t_resp.start()
        t_resp.complete("I claim it is fixed.")

        res = verifier.verify(
            tasks=[t_resp, t_shell],
            response_text="I claim it is fixed.",
            user_input="Fix the calculator so tests pass",
        )
        assert not res.succeeded
        assert res.status == VerificationStatus.FAILED
        assert any("Test execution reported failures" in d for d in res.details)

    # 21. CHAT does not invoke shell
    def test_21_chat_does_not_invoke_shell(self, tmp_path: Path):
        agent, _, _, _ = build_swe_test_agent(tmp_path)
        tasks = agent.run("Hello JARVIS, what is a Python list?", intent=IntentType.CHAT)
        assert not any(t.tool == "shell" for t in tasks)
        assert all(t.tool == "system" for t in tasks)

    # 22. MEMORY does not invoke shell
    def test_22_memory_does_not_invoke_shell(self, tmp_path: Path):
        agent, _, _, _ = build_swe_test_agent(tmp_path)
        tasks = agent.run("Remember that my test framework is pytest", intent=IntentType.MEMORY)
        assert not any(t.tool == "shell" for t in tasks)

    # 23. session continuity works for SWE follow-up
    def test_23_session_continuity_works_for_swe_follow_up(self, tmp_path: Path):
        code_file = tmp_path / "calculator.py"
        code_file.write_text("def add(a, b): return a + b\n", encoding="utf-8")
        test_file = tmp_path / "test_calculator.py"
        test_file.write_text("from calculator import add\ndef test_add(): assert add(2, 3) == 5\n", encoding="utf-8")

        prov = MockSWEProvider(responses=[
            {"type": "ACTION", "tool": "file", "action": "read_file", "parameters": {"path": str(code_file)}},
            {"type": "ACTION", "tool": "shell", "action": "run", "parameters": {"command": f"pytest {test_file}"}},
        ])
        agent, _, _, _ = build_swe_test_agent(tmp_path, provider=prov)

        sid = "swe_sess_cont"
        # Turn 1: inspect
        agent.run(f"Inspect {code_file.name}", session_id=sid, intent=IntentType.TOOL)
        assert agent.active_session.last_target_file == str(code_file)

        # Turn 2: run tests via cross-turn continuity
        tasks2 = agent.run("run its tests", session_id=sid, intent=IntentType.TOOL)
        assert agent.last_trace.session_turn == 2
        assert any(t.tool == "shell" for t in tasks2)

    # 24. request trace records shell events
    def test_24_request_trace_records_shell_events(self, tmp_path: Path):
        prov = MockSWEProvider(responses=[
            {"type": "ACTION", "tool": "shell", "action": "run", "parameters": {"command": "echo trace_test"}},
        ])
        agent, _, _, _ = build_swe_test_agent(tmp_path, provider=prov)
        agent.run("Run echo", intent=IntentType.TOOL)
        trace = agent.last_trace
        assert trace is not None
        assert any(tc.tool == "shell" for tc in trace.tool_calls)
        summary = trace.summary()
        assert summary["status"] == "success"

    # 25. policy decision recorded for shell execution
    def test_25_policy_decision_recorded_for_shell_execution(self, tmp_path: Path):
        prov = MockSWEProvider(responses=[
            {"type": "ACTION", "tool": "shell", "action": "run", "parameters": {"command": "echo policy_recorded"}},
        ])
        agent, _, _, _ = build_swe_test_agent(tmp_path, provider=prov)
        agent.run("Run echo", intent=IntentType.TOOL)
        trace = agent.last_trace
        assert len(trace.policy_decisions) >= 1
        assert any(p.tool == "shell" for p in trace.policy_decisions)
        assert trace.policy_decisions[0].verdict == "allow"
