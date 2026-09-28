"""
Federation Transport Layer.

Handles the network layer abstraction for transmitting payloads between nodes.
"""
import logging
from typing import Any
from .models import FederatedMission, SyncPayload, FederationNode
from .exceptions import NodeOfflineError

logger = logging.getLogger(__name__)

class TransportLayer:
    """Network abstraction (Stub for gRPC/REST/WebSockets)."""

    def send_mission(self, node: FederationNode, mission: FederatedMission) -> None:
        """Send a mission to a remote node."""
        if node.state.value == "offline":
            raise NodeOfflineError(f"Cannot send mission to offline node {node.id}")
            
        logger.info(f"[NETWORK] Sending mission {mission.mission_id} to {node.id}")
        # Stub: send bytes over wire

    def broadcast_sync(self, active_nodes: list[FederationNode], payload: SyncPayload) -> None:
        """Broadcast state sync to all active nodes."""
        for node in active_nodes:
            if node.id != payload.source_node_id:
                logger.debug(f"[NETWORK] Broadcasting {payload.state_type} state sync to {node.id}")
                # Stub: send bytes over wire
