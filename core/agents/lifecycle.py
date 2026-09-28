import logging
from dataclasses import replace

from core.agents.models import AgentResult, AgentTask
from core.mission.enums import MissionPriority, MissionStatus
from core.mission.manager import MissionManager
from core.mission.models import Mission
from core.models.primitives import Identifier

logger = logging.getLogger(__name__)

class AgentLifecycleAdapter:
    """
    Bridges the Agent execution flow with JARVIS Mission Control.
    Each dispatched agent task corresponds to a Child Mission.
    """
    
    def __init__(self, mission_manager: MissionManager):
        self._mission_manager = mission_manager

    def start_child_mission(self, task: AgentTask, parent_mission_id: Identifier, agent_role: str) -> Mission:
        """Registers a new child mission for the delegated agent task."""
        mission = Mission(
            mission_id=Identifier(f"mission_agent_{task.id.value}"),
            title=f"[{agent_role}] {task.intent}",
            description=f"Automated task delegated to {agent_role} agent.",
            priority=MissionPriority.NORMAL,
            parent_mission_id=parent_mission_id,
        )
        
        # We assume the repository saves it on initialization, but we use the manager to transition.
        # Actually, MissionManager requires transitioning from CREATED -> QUEUED -> PLANNING -> READY -> RUNNING
        
        self._mission_manager._repository.save(mission) # Save initial state
        
        try:
            mission = self._mission_manager._transition_status(mission, MissionStatus.QUEUED)
            mission = self._mission_manager._transition_status(mission, MissionStatus.PLANNING)
            mission = self._mission_manager._transition_status(mission, MissionStatus.READY)
            mission = self._mission_manager._transition_status(mission, MissionStatus.RUNNING)
        except Exception as e:
            logger.error(f"Failed to transition child mission for agent: {e}")
            
        return mission

    def complete_child_mission(self, mission: Mission, result: AgentResult) -> None:
        """Transitions the child mission based on the agent's execution result."""
        final_status = MissionStatus.COMPLETED if result.status == "COMPLETED" else MissionStatus.FAILED
        try:
            self._mission_manager._transition_status(mission, final_status)
        except Exception as e:
            logger.error(f"Failed to close child mission {mission.mission_id.value}: {e}")
