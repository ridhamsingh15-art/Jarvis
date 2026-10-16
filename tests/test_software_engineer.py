"""
Tests for the Autonomous Software Engineering Framework.
"""
from unittest.mock import Mock, patch

import pytest

from applications.software_engineer.coordinator import SoftwareEngineeringCoordinator
from applications.software_engineer.exceptions import QualityGateError
from applications.software_engineer.git_manager import GitManager
from applications.software_engineer.models import (
    CodeReviewReport,
    DependencyGraph,
    EngineeringMissionContext,
    EngineeringPhase,
    ImplementationResult,
    RepositoryAnalysis,
    TestResult,
)
from applications.software_engineer.quality_manager import QualityManager


class TestQualityManager:
    def test_quality_gate_fails_without_checkpoint(self):
        qm = QualityManager()
        with pytest.raises(QualityGateError):
            qm.check_quality_gate()

    def test_quality_gate_passes_with_checkpoint(self):
        qm = QualityManager()
        qm.record_checkpoint()
        qm.check_quality_gate()  # Should not raise

class TestGitManager:
    @patch("applications.software_engineer.git_manager.subprocess.run")
    def test_create_checkpoint(self, mock_run):
        # Mock subprocess.run for git status to show changes
        mock_status = Mock()
        mock_status.stdout = " M some_file.py"
        
        mock_commit = Mock()
        mock_commit.stdout = ""
        
        mock_rev_parse = Mock()
        mock_rev_parse.stdout = "abc123def456"
        
        mock_run.side_effect = [
            Mock(stdout=""), # git add
            mock_status,     # git status
            mock_commit,     # git commit
            mock_rev_parse   # git rev-parse
        ]
        
        # Need to mock os.path.exists so it thinks it's a git repo
        with patch("os.path.exists", return_value=True):
            git = GitManager("/fake/path")
            commit_hash = git.create_checkpoint("Test checkpoint")
            
        assert commit_hash == "abc123def456"
        assert mock_run.call_count == 4

class TestCoordinator:
    @patch("applications.software_engineer.coordinator.GitManager")
    @patch("applications.software_engineer.coordinator.QualityManager")
    def test_execute_mission_fails_and_stops_when_tests_fail(self, MockQuality, MockGit):
        coordinator = SoftwareEngineeringCoordinator(
            llm_client=Mock(),
            workspace_path="/fake/path",
            git_manager=MockGit.return_value,
            quality_manager=MockQuality.return_value,
        )
        coordinator._planner.plan_phases = Mock(return_value=[
            EngineeringPhase.ANALYSIS,
            EngineeringPhase.DESIGN,
            EngineeringPhase.GENERATION,
            EngineeringPhase.REVIEW,
            EngineeringPhase.TESTING,
            EngineeringPhase.DOCUMENTATION,
        ])
        coordinator._analyzer.analyze = Mock(return_value=RepositoryAnalysis(
            dependency_graph=DependencyGraph(modules=[], imports={}),
            primary_language="Python",
            detected_frameworks=[],
            entry_points=[],
            relevant_files=[],
        ))
        coordinator._designer.design = Mock(return_value=Mock())
        coordinator._generator.generate = Mock(return_value=ImplementationResult(
            diffs=[], files_touched=[], compile_success=True,
        ))
        coordinator._reviewer.review = Mock(return_value=CodeReviewReport(
            approved=True, comments=[],
        ))
        coordinator._tester.run_tests = Mock(return_value=TestResult(
            passed=False,
            total_tests=4,
            passed_tests=3,
            failed_tests=1,
            failure_messages=["test_checkout failed"],
        ))
        coordinator._documenter.document_changes = Mock()
        MockGit.return_value.create_checkpoint.return_value = "checkpoint-hash"

        report = coordinator.execute_mission(
            EngineeringMissionContext(workspace_path="/fake/path", goal="Test goal")
        )

        assert report.success is False
        assert "test_checkout failed" in report.summary
        assert report.phases_executed[-1] == EngineeringPhase.TESTING
        assert EngineeringPhase.DOCUMENTATION not in report.phases_executed
        assert coordinator._documenter.document_changes.call_count == 0
        assert MockGit.return_value.create_checkpoint.call_count == 1

    @patch("applications.software_engineer.coordinator.GitManager")
    @patch("applications.software_engineer.coordinator.QualityManager")
    def test_execute_mission_stops_when_generation_fails(self, MockQuality, MockGit):
        coordinator = SoftwareEngineeringCoordinator(
            llm_client=Mock(),
            workspace_path="/fake/path",
            git_manager=MockGit.return_value,
            quality_manager=MockQuality.return_value,
        )
        coordinator._planner.plan_phases = Mock(return_value=[
            EngineeringPhase.ANALYSIS,
            EngineeringPhase.DESIGN,
            EngineeringPhase.GENERATION,
            EngineeringPhase.REVIEW,
            EngineeringPhase.TESTING,
            EngineeringPhase.DOCUMENTATION,
        ])
        coordinator._analyzer.analyze = Mock(return_value=RepositoryAnalysis(
            dependency_graph=DependencyGraph(modules=[], imports={}),
            primary_language="Python",
            detected_frameworks=[],
            entry_points=[],
            relevant_files=[],
        ))
        coordinator._designer.design = Mock(return_value=Mock())
        coordinator._generator.generate = Mock(return_value=ImplementationResult(
            diffs=[], files_touched=["not-written.py"], compile_success=False,
            errors=["generator is unavailable"],
        ))
        coordinator._reviewer.review = Mock(return_value=CodeReviewReport(
            approved=True, comments=[],
        ))
        coordinator._tester.run_tests = Mock(return_value=TestResult(
            passed=True, total_tests=1, passed_tests=1, failed_tests=0,
        ))
        coordinator._documenter.document_changes = Mock()
        MockGit.return_value.create_checkpoint.return_value = "checkpoint-hash"

        report = coordinator.execute_mission(
            EngineeringMissionContext(workspace_path="/fake/path", goal="Test goal")
        )

        assert report.success is False
        assert "generator is unavailable" in report.summary
        assert report.phases_executed[-1] == EngineeringPhase.GENERATION
        assert report.files_modified == []
        coordinator._reviewer.review.assert_not_called()
        coordinator._tester.run_tests.assert_not_called()
        coordinator._documenter.document_changes.assert_not_called()
        assert MockGit.return_value.create_checkpoint.call_count == 1

    @patch("applications.software_engineer.coordinator.GitManager")
    @patch("applications.software_engineer.coordinator.QualityManager")
    def test_execute_mission_continues_after_passing_tests(self, MockQuality, MockGit):
        coordinator = SoftwareEngineeringCoordinator(
            llm_client=Mock(),
            workspace_path="/fake/path",
            git_manager=MockGit.return_value,
            quality_manager=MockQuality.return_value,
        )
        coordinator._planner.plan_phases = Mock(return_value=[
            EngineeringPhase.ANALYSIS,
            EngineeringPhase.DESIGN,
            EngineeringPhase.GENERATION,
            EngineeringPhase.REVIEW,
            EngineeringPhase.TESTING,
            EngineeringPhase.DOCUMENTATION,
        ])
        coordinator._analyzer.analyze = Mock(return_value=RepositoryAnalysis(
            dependency_graph=DependencyGraph(modules=[], imports={}),
            primary_language="Python",
            detected_frameworks=[],
            entry_points=[],
            relevant_files=[],
        ))
        coordinator._designer.design = Mock(return_value=Mock())
        coordinator._generator.generate = Mock(return_value=ImplementationResult(
            diffs=[], files_touched=[], compile_success=True,
        ))
        coordinator._reviewer.review = Mock(return_value=CodeReviewReport(
            approved=True, comments=[],
        ))
        coordinator._tester.run_tests = Mock(return_value=TestResult(
            passed=True,
            total_tests=4,
            passed_tests=4,
            failed_tests=0,
            failure_messages=[],
        ))
        coordinator._documenter.document_changes = Mock()
        MockGit.return_value.create_checkpoint.return_value = "checkpoint-hash"

        report = coordinator.execute_mission(
            EngineeringMissionContext(workspace_path="/fake/path", goal="Test goal")
        )

        assert report.success is True
        assert report.phases_executed[-1] == EngineeringPhase.DOCUMENTATION
        assert coordinator._documenter.document_changes.call_count == 1
        assert MockGit.return_value.create_checkpoint.call_count == 2

    @patch("applications.software_engineer.coordinator.GitManager")
    @patch("applications.software_engineer.coordinator.QualityManager")
    def test_execute_mission_success(self, MockQuality, MockGit):
        mock_git = MockGit.return_value
        mock_quality = MockQuality.return_value
        
        coordinator = SoftwareEngineeringCoordinator(
            llm_client=Mock(),
            workspace_path="/fake/path",
            git_manager=mock_git,
            quality_manager=mock_quality
        )
        
        # Mock the planner to return a short lifecycle
        coordinator._planner.plan_phases = Mock(return_value=[
            EngineeringPhase.ANALYSIS,
            EngineeringPhase.GENERATION,
            EngineeringPhase.REVIEW
        ])
        
        # Mock analysis
        coordinator._analyzer.analyze = Mock(return_value=RepositoryAnalysis(
            dependency_graph=DependencyGraph(modules=[], imports={}),
            primary_language="Python",
            detected_frameworks=[],
            entry_points=[],
            relevant_files=[]
        ))
        
        # Mock generation
        coordinator._generator.generate = Mock(return_value=ImplementationResult(
            diffs=[], files_touched=["test.py"], compile_success=True
        ))
        
        # Mock review
        coordinator._reviewer.review = Mock(return_value=CodeReviewReport(
            approved=True, comments=[]
        ))
        
        context = EngineeringMissionContext(workspace_path="/fake/path", goal="Test goal")
        report = coordinator.execute_mission(context)
        
        assert report.success is True
        assert len(report.phases_executed) == 3
        assert "test.py" in report.files_modified
        
        # Verify checkpointing logic
        assert mock_git.create_checkpoint.call_count == 2 # Pre-gen and post-mission
        assert mock_quality.record_checkpoint.call_count == 1
        assert mock_quality.check_quality_gate.call_count == 1
