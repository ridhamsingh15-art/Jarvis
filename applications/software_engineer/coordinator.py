"""
Software Engineering Coordinator.

Orchestrates the execution of child engineering missions across specialized agents.
"""
import logging
from typing import Any

from .architecture_designer import ArchitectureDesigner
from .code_generator import CodeGenerator
from .code_reviewer import CodeReviewer
from .documentation_engine import DocumentationEngine
from .exceptions import (
    ImplementationFailureError,
    ReviewRejectionError,
    TestFailureError,
)
from .git_manager import GitManager
from .models import (
    EngineeringMissionContext,
    EngineeringPhase,
    EngineeringReport,
)
from .planner import SoftwareEngineeringPlanner
from .quality_manager import QualityManager
from .repository_analyzer import RepositoryAnalyzer
from .test_engine import TestEngine

logger = logging.getLogger(__name__)

class SoftwareEngineeringCoordinator:
    """Orchestrates the entire software engineering workflow."""

    def __init__(
        self,
        llm_client: Any,
        workspace_path: str,
        git_manager: GitManager,
        quality_manager: QualityManager
    ):
        self._llm_client = llm_client
        self._workspace_path = workspace_path
        self._git = git_manager
        self._quality = quality_manager
        
        self._planner = SoftwareEngineeringPlanner(llm_client)
        self._analyzer = RepositoryAnalyzer(workspace_path)
        self._designer = ArchitectureDesigner(llm_client)
        self._generator = CodeGenerator(llm_client, workspace_path)
        self._reviewer = CodeReviewer(llm_client, workspace_path)
        self._tester = TestEngine(llm_client, workspace_path)
        self._documenter = DocumentationEngine(llm_client, workspace_path)

    def execute_mission(self, context: EngineeringMissionContext) -> EngineeringReport:
        logger.info(f"Starting engineering mission {context.mission_id} for goal: {context.goal}")
        
        # Determine phases
        phases = self._planner.plan_phases(context.goal)
        logger.info(f"Planned phases: {[p.value for p in phases]}")
        
        analysis = None
        design = None
        implementation = None
        
        executed_phases = []
        files_modified = []
        
        try:
            for phase in phases:
                executed_phases.append(phase)
                
                if phase == EngineeringPhase.ANALYSIS:
                    analysis = self._analyzer.analyze()
                    
                elif phase == EngineeringPhase.DESIGN:
                    design = self._designer.design(context.goal, analysis)
                    
                elif phase == EngineeringPhase.GENERATION:
                    # Enforce checkpoint before generation
                    self._git.create_checkpoint(f"Pre-generation checkpoint for mission {context.mission_id}")
                    self._quality.record_checkpoint()
                    
                    implementation = self._generator.generate(design)
                    if not implementation.compile_success:
                        details = "; ".join(error for error in implementation.errors if error.strip())
                        raise ImplementationFailureError(
                            "Code generation did not produce a successful implementation: "
                            f"{details or 'no failure details were provided'}"
                        )
                    files_modified.extend(implementation.files_touched)
                    
                elif phase == EngineeringPhase.REVIEW:
                    review = self._reviewer.review(implementation)
                    if not review.approved:
                        raise ReviewRejectionError(f"Code review failed: {review.comments}")
                        
                elif phase == EngineeringPhase.TESTING:
                    test_result = self._tester.run_tests()
                    if not test_result.passed:
                        details = "; ".join(
                            message.strip()
                            for message in test_result.failure_messages[:5]
                            if message.strip()
                        )
                        if not details:
                            details = (
                                f"{test_result.failed_tests} failed out of "
                                f"{test_result.total_tests} tests"
                            )
                        raise TestFailureError(
                            "Automated tests failed "
                            f"({test_result.passed_tests}/{test_result.total_tests} passed): "
                            f"{details[:2000]}"
                        )
                        
                elif phase == EngineeringPhase.DOCUMENTATION:
                    self._documenter.document_changes(implementation, analysis)
            
            # Final quality gate
            self._quality.check_quality_gate()
            
            # Final checkpoint
            final_commit = self._git.create_checkpoint(f"Completed mission {context.mission_id}")
            
            return EngineeringReport(
                mission_id=context.mission_id,
                success=True,
                phases_executed=executed_phases,
                files_modified=files_modified,
                final_commit_hash=final_commit,
                summary=f"Successfully completed {len(executed_phases)} phases."
            )
            
        # This boundary must convert any phase failure into a failed mission report.
        except Exception as e:  # noqa: BLE001
            logger.error(f"Mission failed during phase {executed_phases[-1] if executed_phases else 'init'}: {e}")
            return EngineeringReport(
                mission_id=context.mission_id,
                success=False,
                phases_executed=executed_phases,
                files_modified=files_modified,
                summary=str(e)
            )
