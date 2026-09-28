"""
Federation Mission Scheduler.

Evaluates missions and matches them to the optimal node in the registry.
"""
import logging
from typing import Optional
from .models import FederatedMission, FederationNode
from .registry import NodeRegistry
from .exceptions import DelegationFailedError

logger = logging.getLogger(__name__)

class FederationScheduler:
    """Matches missions to nodes based on requirements and capabilities."""

    def __init__(self, registry: NodeRegistry):
        self._registry = registry

    def schedule_mission(self, mission: FederatedMission) -> FederationNode:
        """
        Find the optimal node for the mission.
        Raises DelegationFailedError if no suitable node is found.
        """
        logger.info(f"Scheduling mission {mission.mission_id} (Requires GPU: {mission.required_gpu}, Min RAM: {mission.min_memory_gb}GB)")
        
        active_nodes = self._registry.get_active_nodes()
        if not active_nodes:
            raise DelegationFailedError("No active nodes available in the federation.")
            
        candidates = []
        for node in active_nodes:
            if node.capabilities.meets_requirements(mission.required_gpu, mission.min_memory_gb):
                candidates.append(node)
                
        if not candidates:
            raise DelegationFailedError(f"No active node meets the requirements for mission {mission.mission_id}.")
            
        # Optimization logic: sort by available memory for now
        candidates.sort(key=lambda n: n.capabilities.memory_gb, reverse=True)
        
        best_node = candidates[0]
        logger.info(f"Mission {mission.mission_id} assigned to {best_node.id} ({best_node.name})")
        return best_node
