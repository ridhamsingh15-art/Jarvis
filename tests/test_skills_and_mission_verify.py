"""
Phase I + J Tests — Skills Runtime and Mission Verification

Phase I — Skills Runtime:
1. skill discovery with matching skill
2. no match returns empty list
3. SkillsRuntime failure isolated
4. tool permission check passes for safe tool
5. tool permission check denies for restricted tool
6. context block formatted correctly

Phase J — Mission Completion Verifier:
1. successful mission (all tasks complete, response present)
2. partial mission (some tasks fail)
3. failed mission (all tasks fail, no response)
4. file existence check (file exists / not exists)
5. custom check passes
6. custom check fails
7. custom check crash handled
8. verification timeout not applicable (sync)
9. LLM-only approval not sufficient (structural check always runs)
"""
import pytest
from unittest.mock import MagicMock
from core.task import Task, TaskStatus
from core.mission_verifier import (
    MissionCompletionVerifier,
    VerificationStatus,
    FileExistsCheck,
    CustomCheck,
    ToolSucceededCheck,
    ResponsePresentCheck,
)
from core.skills_runtime import SkillsRuntime, SkillContext


# ---------------------------------------------------------------------------
# Phase I — Skills Runtime
# ---------------------------------------------------------------------------


def _make_skill(name="TestSkill", description="Does testing", skill_id="skill_001"):
    skill = MagicMock()
    skill.id = MagicMock()
    skill.id.value = skill_id
    skill.name = name
    skill.description = description
    skill.tags = ["test", "demo"]
    skill.instructions = "Run the test suite."
    skill.tools = ["browser"]
    return skill


def _make_match(skill, score=0.9):
    match = MagicMock()
    match.skill = skill
    match.score = score
    return match


class TestSkillsRuntime:
    def test_matching_skill_returned(self):
        skill_mgr = MagicMock()
        skill = _make_skill()
        skill_mgr.match_skill.return_value = [_make_match(skill)]

        runtime = SkillsRuntime(skill_manager=skill_mgr)
        results = runtime.find_skills_for("run some tests")
        assert len(results) == 1
        assert results[0].name == "TestSkill"

    def test_no_match_returns_empty(self):
        skill_mgr = MagicMock()
        skill_mgr.match_skill.return_value = []

        runtime = SkillsRuntime(skill_manager=skill_mgr)
        results = runtime.find_skills_for("something irrelevant")
        assert results == []

    def test_no_skill_manager_returns_empty(self):
        runtime = SkillsRuntime(skill_manager=None)
        results = runtime.find_skills_for("any input")
        assert results == []

    def test_skill_manager_failure_isolated(self):
        skill_mgr = MagicMock()
        skill_mgr.match_skill.side_effect = RuntimeError("DB error")
        runtime = SkillsRuntime(skill_manager=skill_mgr)
        # Must not raise
        results = runtime.find_skills_for("anything")
        assert results == []

    def test_max_skills_respected(self):
        skill_mgr = MagicMock()
        skills = [_make_skill(f"Skill{i}", skill_id=f"s{i}") for i in range(5)]
        skill_mgr.match_skill.return_value = [_make_match(s) for s in skills]

        runtime = SkillsRuntime(skill_manager=skill_mgr, max_skills=2)
        results = runtime.find_skills_for("anything")
        assert len(results) == 2

    def test_context_block_formatted(self):
        ctx = SkillContext(
            skill_id="s1", name="PythonHelper",
            description="Helps with Python",
            tags=["python", "code"],
            instructions="Use pytest to run tests.",
            tools_hint=["browser"],
        )
        block = ctx.to_context_block()
        assert "PythonHelper" in block
        assert "pytest" in block
        assert "browser" in block

    def test_tool_permission_allowed_by_policy(self):
        from core.execution_policy import ExecutionPolicy
        policy = ExecutionPolicy()
        runtime = SkillsRuntime(execution_policy=policy)
        allowed = runtime.check_tool_permission("browser", "open_url", "skill_001")
        assert allowed is True

    def test_tool_permission_denied_by_policy(self):
        from core.execution_policy import ExecutionPolicy, CapabilitySource
        policy = ExecutionPolicy()
        runtime = SkillsRuntime(execution_policy=policy)
        # SKILL source trying to use 'unknown_tool' → denied
        denied = runtime.check_tool_permission("unknown_tool", "do_thing", "skill_001")
        assert denied is False

    def test_format_context_for_prompt(self):
        runtime = SkillsRuntime()
        ctxs = [
            SkillContext("s1", "Skill1", "Does A", tags=["a"]),
            SkillContext("s2", "Skill2", "Does B", tags=["b"]),
        ]
        prompt_block = runtime.format_context_for_prompt(ctxs)
        assert "Skill1" in prompt_block
        assert "Skill2" in prompt_block
        assert "ACTIVE SKILLS" in prompt_block

    def test_empty_context_returns_empty_string(self):
        runtime = SkillsRuntime()
        assert runtime.format_context_for_prompt([]) == ""


# ---------------------------------------------------------------------------
# Phase J — Mission Completion Verifier
# ---------------------------------------------------------------------------


def _complete_task(tool="file", action="read_file", result="file content"):
    t = Task(tool=tool, action=action, args={"path": "/tmp/test"})
    t.start()
    t.complete(result)
    return t


def _failed_task(tool="file", action="read_file", error="not found"):
    t = Task(tool=tool, action=action, args={"path": "/tmp/test"})
    t.start()
    t.fail(error)
    return t


def _respond_task(message="Here is the full research report on AI trends."):
    t = Task(tool="system", action="respond", args={"message": message})
    t.start()
    t.complete(message)
    return t


class TestMissionVerifier:
    def test_success_all_checks_pass(self):
        verifier = MissionCompletionVerifier()
        tasks = [_complete_task(), _respond_task()]
        result = verifier.verify(tasks=tasks, response_text="Here is the full research report.")
        assert result.succeeded
        assert result.status == VerificationStatus.PASSED
        assert result.checks_failed == 0

    def test_failed_tasks_fail_verification(self):
        verifier = MissionCompletionVerifier()
        tasks = [_failed_task()]
        result = verifier.verify(tasks=tasks, response_text="I tried but failed.")
        assert not result.succeeded
        assert result.checks_failed >= 1

    def test_no_response_fails_check(self):
        verifier = MissionCompletionVerifier()
        tasks = [_complete_task()]
        result = verifier.verify(tasks=tasks, response_text="")
        # ResponsePresentCheck fails
        fail_lines = [d for d in result.details if "FAIL" in d and "ResponsePresent" in d]
        assert len(fail_lines) >= 1

    def test_short_response_fails_check(self):
        verifier = MissionCompletionVerifier()
        tasks = [_respond_task(message="ok")]  # < min_length=10
        result = verifier.verify(tasks=tasks, response_text="ok")
        fail_lines = [d for d in result.details if "FAIL" in d]
        assert len(fail_lines) >= 1

    def test_partial_mission_status(self):
        verifier = MissionCompletionVerifier()
        tasks = [_failed_task(), _respond_task("Here is a long enough response for the check.")]
        result = verifier.verify(tasks=tasks, response_text="Here is a long enough response.")
        assert result.status in (VerificationStatus.FAILED, VerificationStatus.PARTIAL)

    def test_file_exists_check_passes(self, tmp_path):
        test_file = tmp_path / "output.txt"
        test_file.write_text("done")
        verifier = MissionCompletionVerifier()
        result = verifier.verify(
            tasks=[_respond_task()],
            response_text="Done. See output.txt",
            expected_files=[str(test_file)],
        )
        file_checks = [d for d in result.details if "FileExists" in d]
        assert any("PASS" in d for d in file_checks)

    def test_file_exists_check_fails(self, tmp_path):
        verifier = MissionCompletionVerifier()
        result = verifier.verify(
            tasks=[_respond_task()],
            response_text="Done.",
            expected_files=[str(tmp_path / "nonexistent.txt")],
        )
        file_checks = [d for d in result.details if "FileExists" in d]
        assert any("FAIL" in d for d in file_checks)

    def test_custom_check_passes(self):
        def my_check(tasks, response_text, **_):
            return True, "Custom condition met"

        verifier = MissionCompletionVerifier()
        result = verifier.verify(
            tasks=[_complete_task(), _respond_task()],
            response_text="Full response here for length.",
            custom_checks=[my_check],
        )
        custom_lines = [d for d in result.details if "Custom" in d or "my_check" in d]
        assert any("PASS" in d for d in custom_lines)

    def test_custom_check_fails(self):
        def bad_condition(tasks, response_text, **_):
            return False, "Condition not met"

        verifier = MissionCompletionVerifier()
        result = verifier.verify(tasks=[_respond_task()], custom_checks=[bad_condition])
        assert result.checks_failed >= 1

    def test_crashing_custom_check_handled(self):
        def crash_check(**kwargs):
            raise RuntimeError("check crashed")

        verifier = MissionCompletionVerifier()
        # Must not raise
        result = verifier.verify(tasks=[], custom_checks=[crash_check])
        crash_lines = [d for d in result.details if "FAIL" in d]
        assert len(crash_lines) >= 1

    def test_recommendations_present_on_failure(self):
        verifier = MissionCompletionVerifier()
        result = verifier.verify(tasks=[_failed_task()], response_text="")
        if result.status != VerificationStatus.PASSED:
            assert len(result.recommendations) > 0

    def test_only_system_tasks_no_tool_check_needed(self):
        verifier = MissionCompletionVerifier()
        tasks = [_respond_task("This is a complete and detailed response to the user query.")]
        result = verifier.verify(tasks=tasks, response_text="This is a complete and detailed response.")
        # ToolSucceededCheck: only system tasks → passes
        tool_checks = [d for d in result.details if "ToolSucceeded" in d]
        assert any("PASS" in d for d in tool_checks)
