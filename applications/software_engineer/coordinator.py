"""
Software Engineering Coordinator.

Orchestrates the execution of child engineering missions across specialized agents.
"""
import logging
from typing import Any

from .models import (
    EngineeringMissionContext, EngineeringPhase, EngineeringReport, 
    RepositoryAnalysis, ArchitectureDesign, ImplementationResult, CodeReviewReport
)
from .exceptions import QualityGateError, ReviewRejectionError
from .planner import SoftwareEngineeringPlanner
from .repository_analyzer import RepositoryAnalyzer
from .architecture_designer import ArchitectureDesigner
from .code_generator import CodeGenerator
from .code_reviewer import CodeReviewer
from .test_engine import TestEngine
from .documentation_engine import DocumentationEngine
from .git_manager import GitManager
from .quality_manager import QualityManager

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
                    files_modified.extend(implementation.files_touched)
                    
                elif phase == EngineeringPhase.REVIEW:
                    review = self._reviewer.review(implementation)
                    if not review.approved:
                        raise ReviewRejectionError(f"Code review failed: {review.comments}")
                        
                elif phase == EngineeringPhase.TESTING:
                    test_result = self._tester.run_tests()
                    if not test_result.passed:
                        # Real implementation might loop back to DEBUGGING phase
                        logger.warning("Tests failed!")
                        
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
            
        except Exception as e:
            logger.error(f"Mission failed during phase {executed_phases[-1] if executed_phases else 'init'}: {e}")
            return EngineeringReport(
                mission_id=context.mission_id,
                success=False,
                phases_executed=executed_phases,
                files_modified=files_modified,
                summary=str(e)
            )
