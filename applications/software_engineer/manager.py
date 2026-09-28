"""
Software Engineer Manager.

Facade for the Autonomous Software Engineering Framework.
"""
import logging
from typing import Any

from .models import EngineeringMissionContext, EngineeringReport
from .coordinator import SoftwareEngineeringCoordinator
from .git_manager import GitManager
from .quality_manager import QualityManager

logger = logging.getLogger(__name__)

class SoftwareEngineerManager:
    """Central facade for the software engineering framework."""

    def __init__(self, llm_client: Any, workspace_path: str):
        self._workspace_path = workspace_path
        self._llm_client = llm_client
        
        # Core utilities
        self._git_manager = GitManager(workspace_path)
        self._quality_manager = QualityManager()
        
        # Orchestrator
        self._coordinator = SoftwareEngineeringCoordinator(
            llm_client=llm_client,
            workspace_path=workspace_path,
            git_manager=self._git_manager,
            quality_manager=self._quality_manager
        )

    def execute_mission(self, goal: str) -> EngineeringReport:
        """
        Execute a full software engineering mission for a specific goal.
        """
        context = EngineeringMissionContext(
            workspace_path=self._workspace_path,
            goal=goal,
            active_branch=self._git_manager.get_current_commit() # Simplified branch/commit detection
        )
        return self._coordinator.execute_mission(context)
