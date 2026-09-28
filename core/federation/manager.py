"""
Federation Manager.

Facade for the JARVIS Federation subsystem.
"""
import logging
from typing import Any

from .models import FederationNode, FederatedMission, SyncPayload
from .node import LocalNode
from .registry import NodeRegistry
from .discovery import DiscoveryService
from .scheduler import FederationScheduler
from .transport import TransportLayer
from .synchronization import StateSynchronizer
from .security import SecurityManager
from .exceptions import DelegationFailedError

logger = logging.getLogger(__name__)

class FederationManager:
    """Central orchestration facade for the distributed AI platform."""

    def __init__(self, local_node: LocalNode):
        self.local_node = local_node
        self.registry = NodeRegistry()
        self.transport = TransportLayer()
        self.security = SecurityManager()
        
        self.scheduler = FederationScheduler(self.registry)
        self.sync = StateSynchronizer(local_node.get_node_model().id, self.registry, self.transport)
        
        # Self-register local node
        self.registry.register_or_update(local_node.get_node_model())
        
        # Setup Discovery
        self.discovery = DiscoveryService(local_node.get_node_model(), self._on_node_discovered)

    def start(self):
        """Start the federation services."""
        logger.info("Starting Federation Manager...")
        self.discovery.start_broadcasting()

    def stop(self):
        """Stop federation services."""
        logger.info("Stopping Federation Manager...")
        self.discovery.stop_broadcasting()

    def _on_node_discovered(self, remote_node: FederationNode) -> None:
        """Callback when a remote node is found on the network."""
        logger.debug(f"Handling discovery of {remote_node.id}")
        # In a real implementation we would require an auth handshake here
        self.registry.register_or_update(remote_node)

    def delegate_mission(self, mission: FederatedMission) -> str:
        """
        Attempt to delegate a mission to an optimal remote node.
        Returns the ID of the assigned node.
        """
        logger.info(f"Attempting to delegate mission {mission.mission_id}...")
        try:
            target_node = self.scheduler.schedule_mission(mission)
            
            # Encrypt payload if needed
            secure_payload = self.security.encrypt_payload(mission.payload)
            mission_to_send = FederatedMission(
                mission_id=mission.mission_id,
                target_node_id=target_node.id,
                payload={"secure_data": secure_payload},
                required_gpu=mission.required_gpu,
                min_memory_gb=mission.min_memory_gb
            )
            
            self.transport.send_mission(target_node, mission_to_send)
            return target_node.id
            
        except Exception as e:
            logger.error(f"Delegation failed: {e}")
            raise DelegationFailedError(f"Could not delegate mission {mission.mission_id}") from e
