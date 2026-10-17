"""Execute pytest in a workspace and report only metrics supported by its output."""
from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from .models import RepositoryAnalysis, TestResult

logger = logging.getLogger(__name__)
TEST_RUN_TIMEOUT_SECONDS = 300
_SUMMARY_COUNT = re.compile(
    r"(?P<count>\d+)\s+(?P<outcome>passed|failed|errors?|skipped|xfailed|xpassed|deselected)\b",
    re.IGNORECASE,
)
_SUMMARY_DURATION = re.compile(r"\bin\s+\d+(?:\.\d+)?s\b", re.IGNORECASE)


class TestEngine:
    """Agent that executes and summarizes a project's pytest suite."""

    def __init__(self, llm_client: Any, workspace_path: str):
        self._llm_client = llm_client
        self._workspace_path = workspace_path

    @staticmethod
    def _parse_pytest_summary(output: str) -> dict[str, int] | None:
        """Parse the terminal summary line; return None if pytest did not emit one."""
        summary_line = next(
            (
                line.strip()
                for line in reversed(output.splitlines())
                if _SUMMARY_DURATION.search(line)
                and _SUMMARY_COUNT.search(line)
            ),
            None,
        )
        if summary_line is None:
            return None

        counts = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
        }
        for match in _SUMMARY_COUNT.finditer(summary_line):
            count = int(match.group("count"))
            outcome = match.group("outcome").casefold()
            if outcome == "passed":
                counts["passed"] += count
            elif outcome in {"failed", "error", "errors"}:
                # Collection/setup errors are failures too, even when no test body ran.
                counts["failed"] += count
            elif outcome in counts:
                counts[outcome] += count
        return counts

    def run_tests(self) -> TestResult:
        """Run pytest with a bounded timeout and return observed, not guessed, metrics."""
        workspace = Path(self._workspace_path).expanduser().resolve()
        tests_dir = workspace / "tests"
        logger.info("Running pytest in %s", workspace)

        if not workspace.is_dir():
            return TestResult(
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                coverage_percent=None,
                failure_messages=[f"Workspace does not exist: {workspace}"],
            )
        if not tests_dir.is_dir():
            return TestResult(
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                coverage_percent=None,
                failure_messages=[f"Test directory does not exist: {tests_dir}"],
            )

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "tests"],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TEST_RUN_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            message = f"pytest timed out after {TEST_RUN_TIMEOUT_SECONDS} seconds."
            logger.warning(message)
            return TestResult(
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                coverage_percent=None,
                failure_messages=[message],
            )
        except OSError as exc:
            logger.warning("Could not run pytest in %s: %s", workspace, exc)
            return TestResult(
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                coverage_percent=None,
                failure_messages=[f"Could not start pytest: {exc}"],
            )

        output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        summary = self._parse_pytest_summary(output)
        if summary is None:
            passed = False
            total = passed_count = failed_count = 0
            if result.returncode == 0:
                detail = "pytest did not emit a parseable result summary."
            else:
                detail = f"pytest exited with code {result.returncode}."
            if output:
                detail = f"{detail}\n{output[-4000:]}"
            failure_messages = [detail]
        else:
            passed_count = summary["passed"]
            failed_count = summary["failed"]
            total = sum(summary[key] for key in ("passed", "failed", "skipped", "xfailed", "xpassed"))
            passed = result.returncode == 0 and failed_count == 0
            failure_messages = [] if passed else [
                output[-4000:] or f"pytest exited with code {result.returncode}."
            ]

        return TestResult(
            passed=passed,
            total_tests=total,
            passed_tests=passed_count,
            failed_tests=failed_count,
            # Coverage is unknown unless a coverage tool was actually run.
            coverage_percent=None,
            failure_messages=failure_messages,
        )

    def generate_tests(self, analysis: RepositoryAnalysis, target_file: str) -> None:
        """Test generation has no implementation yet; never silently claim it ran."""
        raise NotImplementedError(
            "Automated test generation is not implemented; run_tests() can execute existing tests."
        )
