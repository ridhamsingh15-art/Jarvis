from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from applications.software_engineer.models import DependencyGraph, RepositoryAnalysis
from applications.software_engineer.test_engine import TestEngine as SoftwareTestEngine


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_sample.py").write_text("def test_sample(): assert True\n", encoding="utf-8")
    return tmp_path


def _completed(returncode: int, stdout: str = "", stderr: str = ""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_run_tests_uses_current_interpreter_and_real_pass_skip_counts(workspace):
    output = "3 passed, 2 skipped, 1 xfailed in 0.42s"
    with patch("applications.software_engineer.test_engine.subprocess.run", return_value=_completed(0, output)) as run:
        result = SoftwareTestEngine(None, str(workspace)).run_tests()

    assert result.passed is True
    assert result.total_tests == 6
    assert result.passed_tests == 3
    assert result.failed_tests == 0
    assert result.coverage_percent is None
    assert result.failure_messages == []
    args, kwargs = run.call_args
    assert args[0] == [sys.executable, "-m", "pytest", "-q", "tests"]
    assert kwargs["cwd"] == str(workspace.resolve())
    assert kwargs["timeout"] > 0
    assert kwargs["check"] is False


def test_run_tests_reports_actual_failures(workspace):
    output = "FAILED tests/test_sample.py::test_sample - AssertionError\n1 failed, 2 passed in 0.12s"
    with patch("applications.software_engineer.test_engine.subprocess.run", return_value=_completed(1, output)):
        result = SoftwareTestEngine(None, str(workspace)).run_tests()

    assert result.passed is False
    assert result.total_tests == 3
    assert result.passed_tests == 2
    assert result.failed_tests == 1
    assert "test_sample" in result.failure_messages[0]


def test_run_tests_counts_collection_errors_as_failures(workspace):
    output = "ERROR collecting tests/test_sample.py\n1 error in 0.08s"
    with patch("applications.software_engineer.test_engine.subprocess.run", return_value=_completed(2, output)):
        result = SoftwareTestEngine(None, str(workspace)).run_tests()

    assert result.passed is False
    assert result.total_tests == 1
    assert result.failed_tests == 1
    assert "ERROR collecting" in result.failure_messages[0]


def test_run_tests_handles_timeout_without_fabricating_test_counts(workspace):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    with patch("applications.software_engineer.test_engine.subprocess.run", side_effect=timeout):
        result = SoftwareTestEngine(None, str(workspace)).run_tests()

    assert result.passed is False
    assert result.total_tests == 0
    assert result.passed_tests == 0
    assert result.failed_tests == 0
    assert "timed out" in result.failure_messages[0]
    assert result.coverage_percent is None


def test_run_tests_fails_when_pytest_summary_is_unparseable(workspace):
    with patch("applications.software_engineer.test_engine.subprocess.run", return_value=_completed(0, "unexpected output")):
        result = SoftwareTestEngine(None, str(workspace)).run_tests()

    assert result.passed is False
    assert result.total_tests == 0
    assert "parseable result summary" in result.failure_messages[0]


def test_generate_tests_does_not_silently_claim_success(workspace):
    analysis = RepositoryAnalysis(
        dependency_graph=DependencyGraph(modules=[], imports={}),
        primary_language="Python",
        detected_frameworks=[],
        entry_points=[],
        relevant_files=[],
    )
    engine = SoftwareTestEngine(None, str(workspace))

    with pytest.raises(NotImplementedError, match="not implemented"):
        engine.generate_tests(analysis, "sample.py")


def test_run_tests_rejects_missing_tests_directory(tmp_path):
    result = SoftwareTestEngine(None, str(tmp_path)).run_tests()

    assert result.passed is False
    assert result.total_tests == 0
    assert "Test directory does not exist" in result.failure_messages[0]
