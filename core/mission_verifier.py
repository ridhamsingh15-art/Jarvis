"""
Mission Completion Verifier — Phase J implementation.

A mission is NOT successful merely because:
  - planner completed
  - reasoning completed
  - tools executed
  - response generated

Mission success requires verification against task-specific postconditions.

Verification flow::

    MISSION
        ↓
    PLAN
        ↓
    EXECUTE
        ↓
    OBSERVE     ← MissionCompletionVerifier.verify()
        ↓
    SUCCESS / RECOVER / FAIL

Verification strategies:
    - FileExists:     verify a file/directory exists at expected path
    - ToolSucceeded:  verify all non-system tasks completed
    - ResponsePresent: verify a non-empty useful response was generated
    - Custom:         user-supplied callable postcondition

Design principle:
    LLM self-approval is NOT sufficient. At least one structural check
    must pass before a mission is marked complete.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable

from core.task import Task, TaskStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verification result
# ---------------------------------------------------------------------------


class VerificationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"

    # Aliases for Phase 7C taxonomy
    VERIFIED_COMPLETE = "passed"
    NOT_VERIFIED = "failed"


@dataclass
class VerificationResult:
    status: VerificationStatus
    checks_passed: int
    checks_failed: int
    details: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.status in (VerificationStatus.PASSED, "passed", "VERIFIED_COMPLETE")

    @property
    def partially_succeeded(self) -> bool:
        return self.status in (VerificationStatus.PARTIAL, "partial")

    @property
    def is_verified_complete(self) -> bool:
        return self.succeeded

    @property
    def is_partial(self) -> bool:
        return self.partially_succeeded

    @property
    def is_not_verified(self) -> bool:
        return not self.succeeded


@dataclass
class MissionPostcondition:
    """Explicit declarative postcondition for a mission."""
    check_type: str  # "file_exists", "file_content", "tool_succeeded", "custom"
    target: str = ""
    expected_value: Any = None
    description: str = ""


def get_effective_tasks(tasks: list[Task]) -> list[Task]:
    """Derive the effective final state of tasks, collapsing retried attempts of the same operation.

    Preserves chronological order of the final attempt for each logical operation.
    """
    if not tasks:
        return []

    def _task_key(t: Task) -> tuple:
        args = t.args or {}
        target = (
            args.get("path")
            or args.get("filepath")
            or args.get("file_path")
            or args.get("app")
            or args.get("site")
            or args.get("url")
            or args.get("query")
            or args.get("name")
        )
        if target is not None:
            norm_target = str(target).lower().replace("\\", "/")
            return (t.tool, t.action, norm_target)
        try:
            items = tuple(sorted((k, str(v)) for k, v in args.items() if k not in ("retry_count", "failure_history")))
            return (t.tool, t.action, items)
        except Exception:
            return (t.tool, t.action)

    latest_by_key: dict[tuple, Task] = {}
    key_order: list[tuple] = []

    for t in tasks:
        key = _task_key(t)
        if key not in latest_by_key:
            key_order.append(key)
        latest_by_key[key] = t

    return [latest_by_key[k] for k in key_order]


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


@dataclass
class ToolSucceededCheck:
    """Verify that all non-system tasks completed successfully in their final effective state."""
    name: str = "ToolSucceeded"

    def run(self, tasks: list[Task], **_kwargs: Any) -> tuple[bool, str]:
        if not tasks:
            return True, "No tasks to verify."
        real_tasks = [t for t in tasks if t.tool != "system"]
        if not real_tasks:
            return True, "Only system respond tasks — no tool verification required."
        effective_tasks = get_effective_tasks(real_tasks)
        failed = [t for t in effective_tasks if t.status != TaskStatus.COMPLETED]
        if failed:
            reasons = "; ".join(f"{t.tool}.{t.action} ({t.status.value}): {t.error or 'incomplete'}" for t in failed)
            return False, f"Failed or incomplete tasks: {reasons}"
        recovered_count = len(real_tasks) - len(effective_tasks)
        if recovered_count > 0:
            return True, f"All {len(effective_tasks)} effective tool task(s) completed ({recovered_count} recovered after retry)."
        return True, f"All {len(effective_tasks)} tool task(s) completed."


@dataclass
class ResponsePresentCheck:
    """Verify that a non-empty, useful response was generated."""
    min_length: int = 10
    name: str = "ResponsePresent"

    def run(self, tasks: list[Task], response_text: str = "", **_kwargs: Any) -> tuple[bool, str]:
        # Check explicit response_text first
        if len(str(response_text).strip()) >= self.min_length:
            return True, f"Response present ({len(str(response_text))} chars)."
        for task in tasks:
            if task.tool == "system" and task.action in ("respond", "error"):
                msg = task.result or task.args.get("message", "")
                if len(str(msg).strip()) >= self.min_length:
                    return True, f"Response present ({len(str(msg))} chars)."
        return False, "No meaningful response generated."


@dataclass
class FileExistsCheck:
    """Verify that an expected output file exists."""
    expected_path: str
    name: str = "FileExists"

    def run(self, **_kwargs: Any) -> tuple[bool, str]:
        path = Path(self.expected_path)
        if path.exists():
            return True, f"File exists: {path}"
        return False, f"Expected file not found: {path}"


@dataclass
class FileContentCheck:
    """Verify that an expected output file contains expected content."""
    expected_path: str
    expected_content: str
    name: str = "FileContent"

    def run(self, tasks: list[Task] | None = None, **_kwargs: Any) -> tuple[bool, str]:
        # 1. First check if any executed task (e.g. read_file) already observed the content
        if tasks:
            for t in tasks:
                if t.tool == "file" and t.action in ("read_file", "open_file") and t.status == TaskStatus.COMPLETED:
                    res_str = str(t.result or "")
                    if self.expected_content in res_str:
                        return True, f"Observed expected content in {t.tool}.{t.action} result: '{self.expected_content}'"

        # 2. Check directly on disk if file exists
        path = Path(self.expected_path)
        if not path.exists():
            return False, f"Expected file not found to verify content: {path}"
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            if self.expected_content in content:
                return True, f"File content verified on disk: contains '{self.expected_content}'"
            return False, f"File content mismatch: '{self.expected_content}' not found in {path}"
        except Exception as exc:  # noqa: BLE001
            return False, f"Could not read file {path}: {exc}"


@dataclass
class CustomCheck:
    """A user-supplied callable postcondition."""
    check_fn: Callable[..., tuple[bool, str]]
    name: str = "Custom"

    def run(self, **kwargs: Any) -> tuple[bool, str]:
        try:
            return self.check_fn(**kwargs)
        except Exception as exc:  # noqa: BLE001
            return False, f"Custom check raised: {exc}"


@dataclass
class TestEvidenceCheck:
    """Verify test execution evidence from shell tasks."""
    name: str = "TestEvidence"

    def run(self, tasks: list[Task] | None = None, **_kwargs: Any) -> tuple[bool, str]:
        if not tasks:
            return False, "No tasks executed to evaluate test evidence."

        shell_tasks = [t for t in tasks if t.tool == "shell" and t.action in ("run", "execute", "shell_run")]
        if not shell_tasks:
            return False, "No shell test execution tasks found in mission."

        test_tasks = [
            t for t in shell_tasks
            if any(k in str(t.args.get("command", "") or "").lower() for k in ("pytest", "python -m pytest", "py -m pytest", "test"))
        ]
        if not test_tasks:
            test_tasks = shell_tasks

        latest_test = test_tasks[-1]
        res_str = str(latest_test.result or "")
        err_str = str(latest_test.error or "")

        if latest_test.status != TaskStatus.COMPLETED:
            return False, f"Test task failed to complete: {err_str or res_str[:120]}"

        if "FAILED" in res_str or "ERRORS" in res_str or "[return_code=1]" in res_str:
            return False, f"Test execution reported failures: {res_str[:160]}"

        if "passed" in res_str.lower() or "return_code=0" in res_str:
            return True, f"Test execution verified successful: {res_str[:120].strip()}"

        return True, "Test task completed successfully."


# ---------------------------------------------------------------------------
# MissionCompletionVerifier
# ---------------------------------------------------------------------------


class MissionCompletionVerifier:
    """
    Verifies mission completion against structural postconditions.

    Observational only: NEVER executes tools, NEVER bypasses ExecutionPolicy,
    and NEVER treats model self-claims as proof.
    """

    # Default checks applied when no custom checks are provided
    _DEFAULT_CHECKS = [ToolSucceededCheck, ResponsePresentCheck]

    def __init__(self, extra_checks: list | None = None) -> None:
        self._extra_checks = extra_checks or []

    def verify(
        self,
        tasks: list[Task],
        response_text: str = "",
        expected_files: list[str] | None = None,
        expected_contents: dict[str, str] | None = None,
        custom_checks: list[Callable] | None = None,
        postconditions: list[MissionPostcondition] | None = None,
        user_input: str = "",
    ) -> VerificationResult:
        """
        Run all verification checks against the mission output.

        Args:
            tasks:             Executed Task objects with final statuses.
            response_text:     The final response string shown to the user.
            expected_files:    Paths that must exist for success.
            expected_contents: Dict mapping file paths to expected substrings.
            custom_checks:     Extra callable postconditions.
            postconditions:    Explicit MissionPostcondition list.
            user_input:        Original mission input for context/inference.

        Returns:
            VerificationResult with status, counts, and details.
        """
        checks_to_run = list(self._DEFAULT_CHECKS)
        results: list[tuple[str, bool, str]] = []

        # Deduplicate files and contents
        exp_files = list(expected_files or [])
        exp_contents = dict(expected_contents or {})

        # Process explicit postconditions
        if postconditions:
            for pc in postconditions:
                if pc.check_type == "file_exists" and pc.target:
                    if pc.target not in exp_files:
                        exp_files.append(pc.target)
                elif pc.check_type == "file_content" and pc.target:
                    exp_contents[pc.target] = str(pc.expected_value)
                elif pc.check_type == "custom" and callable(pc.expected_value):
                    custom_checks = list(custom_checks or [])
                    custom_checks.append(pc.expected_value)

        # Automatic inference from tasks/user_input when user_input is provided and none explicitly given
        if not exp_files and not exp_contents and user_input:
            self._infer_postconditions(tasks, user_input, exp_files, exp_contents)

        # Run default checks
        for check_cls in checks_to_run:
            check = check_cls()
            passed, detail = check.run(
                tasks=tasks,
                response_text=response_text,
            )
            results.append((check.name, passed, detail))

        # File existence checks
        for path in exp_files:
            check = FileExistsCheck(expected_path=path)
            passed, detail = check.run(tasks=tasks, response_text=response_text)
            results.append((check.name, passed, detail))

        # File content checks
        for path, exp_text in exp_contents.items():
            check = FileContentCheck(expected_path=path, expected_content=exp_text)
            passed, detail = check.run(tasks=tasks, response_text=response_text)
            results.append((check.name, passed, detail))

        # Custom callable checks
        for fn in (custom_checks or []):
            check = CustomCheck(check_fn=fn, name=getattr(fn, "__name__", "Custom"))
            passed, detail = check.run(tasks=tasks, response_text=response_text)
            results.append((check.name, passed, detail))

        # Test evidence check for software engineering and test missions
        is_test_mission = bool(
            any(isinstance(c, TestEvidenceCheck) for c in (self._extra_checks or []))
            or any(t.tool == "shell" and any(k in str(t.args.get("command", "") or "").lower() for k in ("pytest", "python -m pytest")) for t in tasks)
            or (
                user_input
                and re.search(r"\b(run\s+tests?|run\s+pytest|execute\s+tests?|fix\s+(?:the\s+)?tests?|verify\s+(?:the\s+)?tests?)\b", user_input, re.IGNORECASE)
                and any(t.tool == "shell" for t in tasks)
            )
        )

        if is_test_mission:
            test_check = TestEvidenceCheck()
            passed, detail = test_check.run(tasks=tasks, response_text=response_text)
            results.append((test_check.name, passed, detail))

        # Extra checks registered on construction
        for check in self._extra_checks:
            passed, detail = check.run(tasks=tasks, response_text=response_text)
            results.append((getattr(check, "name", "ExtraCheck"), passed, detail))

        # Tally
        passed_count = sum(1 for _, p, _ in results if p)
        failed_count = sum(1 for _, p, _ in results if not p)
        detail_lines = [f"{'PASS' if p else 'FAIL'} [{name}]: {detail}" for name, p, detail in results]

        # Check for timeout among tasks
        is_timeout = any("timed out after" in str(t.error).lower() for t in tasks if t.tool != "system")

        # Separate structural/deterministic evidence checks from conversational check
        real_tasks = [t for t in tasks if t.tool != "system"]
        effective_tasks = get_effective_tasks(real_tasks)
        has_real_tasks = len(effective_tasks) > 0
        evidence_results = []
        conversational_results = []
        for name, passed, detail in results:
            if name == "ResponsePresent":
                conversational_results.append((name, passed, detail))
            elif name == "ToolSucceeded" and not has_real_tasks:
                # No tool execution occurred; do not count as positive evidence
                continue
            else:
                evidence_results.append((name, passed, detail))

        effective_completed = [t for t in effective_tasks if t.status == TaskStatus.COMPLETED]
        effective_failed = [t for t in effective_tasks if t.status != TaskStatus.COMPLETED]
        has_partial_task_success = len(effective_completed) > 0 and len(effective_failed) > 0

        if is_timeout:
            status = VerificationStatus.TIMEOUT
        elif evidence_results:
            evidence_passed = sum(1 for _, p, _ in evidence_results if p)
            evidence_failed = sum(1 for _, p, _ in evidence_results if not p)
            if any(name == "TestEvidence" and not p for name, p, _ in evidence_results):
                status = VerificationStatus.FAILED
            elif evidence_failed == 0 and not has_partial_task_success:
                status = VerificationStatus.PASSED
            elif (evidence_passed > 0 and evidence_failed > 0) or has_partial_task_success:
                status = VerificationStatus.PARTIAL
            else:
                status = VerificationStatus.FAILED
        else:
            # Zero structural evidence checks (no real tools, no file/content/custom postconditions)
            # Under the grounding invariant: MODEL CLAIMS ARE NOT PROOF.
            # A mission CANNOT be verified complete merely because conversational text was generated.
            status = VerificationStatus.FAILED
            results.append(("MissionEvidence", False, "No actionable tools executed and no verifiable postconditions established."))
            detail_lines.append("FAIL [MissionEvidence]: No actionable tools executed and no verifiable postconditions established.")
            failed_count += 1

        recommendations = []
        if status in (VerificationStatus.FAILED, VerificationStatus.PARTIAL, VerificationStatus.TIMEOUT):
            failed_names = [name for name, p, _ in results if not p]
            recommendations.append(
                f"Failed checks: {', '.join(failed_names) if failed_names else 'Timeout'}. "
                "Review task results and consider retrying or escalating."
            )

        log_level = logging.INFO if status == VerificationStatus.PASSED else logging.WARNING
        logger.log(
            log_level,
            "[MISSION_VERIFY] status=%s passed=%d failed=%d",
            status.value, passed_count, failed_count,
        )
        for line in detail_lines:
            logger.debug("[MISSION_VERIFY] %s", line)

        return VerificationResult(
            status=status,
            checks_passed=passed_count,
            checks_failed=failed_count,
            details=detail_lines,
            recommendations=recommendations,
        )

    def _infer_postconditions(
        self,
        tasks: list[Task],
        user_input: str,
        exp_files: list[str],
        exp_contents: dict[str, str],
    ) -> None:
        """Infer expected files and contents deterministically from tasks and input."""
        import re

        # Extract from tasks
        for t in tasks:
            if t.tool == "file" and t.action in ("create_file", "write_file", "read_file"):
                p = t.args.get("path") or t.args.get("filepath")
                if p and p not in exp_files:
                    exp_files.append(str(p))
                cnt = t.args.get("content")
                if p and cnt and p not in exp_contents:
                    exp_contents[str(p)] = str(cnt)

        # Extract content from user_input (e.g. 'containing HELLO' or 'content "HELLO"')
        if user_input:
            match_content = re.search(
                r"(?:containing|content(?:\s+is|=|\s+to|\s+of)?)\s+['\"]?([A-Za-z0-9_\.\-\s]+?)['\"]?(?:\s+and\b|[,\.]|$)",
                user_input,
                re.IGNORECASE,
            )
            if match_content and exp_files:
                target_content = match_content.group(1).strip()
                if target_content and target_content.lower() not in ("it", "its", "the"):
                    for p in exp_files:
                        if p not in exp_contents:
                            exp_contents[p] = target_content
