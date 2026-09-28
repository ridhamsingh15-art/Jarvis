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


@dataclass
class VerificationResult:
    status: VerificationStatus
    checks_passed: int
    checks_failed: int
    details: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.status == VerificationStatus.PASSED

    @property
    def partially_succeeded(self) -> bool:
        return self.status == VerificationStatus.PARTIAL


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


@dataclass
class ToolSucceededCheck:
    """Verify that all non-system tasks completed successfully."""
    name: str = "ToolSucceeded"

    def run(self, tasks: list[Task], **_kwargs: Any) -> tuple[bool, str]:
        if not tasks:
            return True, "No tasks to verify."
        real_tasks = [t for t in tasks if t.tool != "system"]
        if not real_tasks:
            return True, "Only system respond tasks — no tool verification required."
        failed = [t for t in real_tasks if t.status == TaskStatus.FAILED]
        if failed:
            reasons = "; ".join(f"{t.tool}.{t.action}: {t.error}" for t in failed)
            return False, f"Failed tasks: {reasons}"
        return True, f"All {len(real_tasks)} tool task(s) completed."


@dataclass
class ResponsePresentCheck:
    """Verify that a non-empty, useful response was generated."""
    min_length: int = 10
    name: str = "ResponsePresent"

    def run(self, tasks: list[Task], **_kwargs: Any) -> tuple[bool, str]:
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
class CustomCheck:
    """A user-supplied callable postcondition."""
    check_fn: Callable[..., tuple[bool, str]]
    name: str = "Custom"

    def run(self, **kwargs: Any) -> tuple[bool, str]:
        try:
            return self.check_fn(**kwargs)
        except Exception as exc:  # noqa: BLE001
            return False, f"Custom check raised: {exc}"


# ---------------------------------------------------------------------------
# MissionCompletionVerifier
# ---------------------------------------------------------------------------


class MissionCompletionVerifier:
    """
    Verifies mission completion against structural postconditions.

    Usage::

        verifier = MissionCompletionVerifier()
        result = verifier.verify(
            tasks=executed_tasks,
            response_text=final_response,
        )
        if not result.succeeded:
            # recover or report failure
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
        custom_checks: list[Callable] | None = None,
    ) -> VerificationResult:
        """
        Run all verification checks against the mission output.

        Args:
            tasks:          Executed Task objects with final statuses.
            response_text:  The final response string shown to the user.
            expected_files: Paths that must exist for success.
            custom_checks:  Extra callable postconditions.

        Returns:
            VerificationResult with status, counts, and details.
        """
        checks_to_run = list(self._DEFAULT_CHECKS)
        results: list[tuple[str, bool, str]] = []

        # Run default checks
        for check_cls in checks_to_run:
            check = check_cls()
            passed, detail = check.run(
                tasks=tasks,
                response_text=response_text,
            )
            results.append((check.name, passed, detail))

        # File existence checks
        for path in (expected_files or []):
            check = FileExistsCheck(expected_path=path)
            passed, detail = check.run()
            results.append((check.name, passed, detail))

        # Custom callable checks
        for fn in (custom_checks or []):
            check = CustomCheck(check_fn=fn, name=getattr(fn, "__name__", "Custom"))
            passed, detail = check.run(tasks=tasks, response_text=response_text)
            results.append((check.name, passed, detail))

        # Extra checks registered on construction
        for check in self._extra_checks:
            passed, detail = check.run(tasks=tasks, response_text=response_text)
            results.append((getattr(check, "name", "ExtraCheck"), passed, detail))

        # Tally
        passed_count = sum(1 for _, p, _ in results if p)
        failed_count = sum(1 for _, p, _ in results if not p)
        detail_lines = [f"{'PASS' if p else 'FAIL'} [{name}]: {detail}" for name, p, detail in results]

        # Determine overall status
        if failed_count == 0:
            status = VerificationStatus.PASSED
        elif passed_count == 0:
            status = VerificationStatus.FAILED
        else:
            status = VerificationStatus.PARTIAL

        recommendations = []
        if status in (VerificationStatus.FAILED, VerificationStatus.PARTIAL):
            failed_names = [name for name, p, _ in results if not p]
            recommendations.append(
                f"Failed checks: {', '.join(failed_names)}. "
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
