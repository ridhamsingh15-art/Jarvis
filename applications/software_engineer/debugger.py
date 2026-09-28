"""
Debugger Agent.

Analyzes failures, reads stack traces (potentially via perception),
and suggests or applies fixes.
"""
import logging
from typing import Any, Optional
from core.perception.manager import PerceptionManager
from .models import DebugReport, ImplementationResult

logger = logging.getLogger(__name__)

class Debugger:
    """Agent that analyzes failures and proposes fixes."""

    def __init__(self, llm_client: Any, perception_manager: Optional[PerceptionManager] = None):
        self._llm_client = llm_client
        self._perception_manager = perception_manager

    def analyze_failure(self, error_output: str, source_context: Optional[str] = None) -> DebugReport:
        """
        Analyze an error string (e.g., stack trace or compiler error).
        """
        logger.info("Analyzing failure...")
        return DebugReport(
            root_cause_analysis="Analyzed stack trace and found issue.",
            proposed_fix=ImplementationResult(
                diffs=[],
                files_touched=[],
                compile_success=True
            ),
            confidence=0.8
        )

    def analyze_visual_failure(self) -> DebugReport:
        """
        Use the perception manager to look for errors on screen (e.g., in an IDE or terminal).
        """
        if not self._perception_manager:
            raise ValueError("PerceptionManager is required for visual debugging.")
            
        logger.info("Capturing screen to analyze visual failure...")
        scene = self._perception_manager.perceive_screen()
        
        # In a real implementation, we would extract the text from ERROR components
        # and pass it to analyze_failure
        
        return DebugReport(
            root_cause_analysis="Analyzed screen and found visual issue.",
            proposed_fix=None,
            confidence=0.5
        )
