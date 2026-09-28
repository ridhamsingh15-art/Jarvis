"""
Federation Node Registry.

Tracks active trusted nodes in the network and caches their capabilities.
"""
import logging
import time
from typing import Optional
from .models import FederationNode, NodeState

logger = logging.getLogger(__name__)

class NodeRegistry:
    """Registry of known federation peers."""

    def __init__(self):
        self._nodes: dict[str, FederationNode] = {}
        self._offline_threshold_seconds = 30.0

    def register_or_update(self, node: FederationNode) -> None:
        """Register a new node or update its heartbeat and state."""
        if node.id not in self._nodes:
            logger.info(f"New node discovered: {node.name} ({node.id})")
        else:
            logger.debug(f"Heartbeat received from {node.id}")
            
        self._nodes[node.id] = node

    def remove_node(self, node_id: str) -> None:
        """Explicitly remove a node from the registry."""
        if node_id in self._nodes:
            logger.info(f"Removing node from registry: {node_id}")
            del self._nodes[node_id]

    def get_node(self, node_id: str) -> Optional[FederationNode]:
        """Retrieve a specific node."""
        return self._nodes.get(node_id)

    def get_active_nodes(self) -> list[FederationNode]:
        """Retrieve all nodes considered online."""
        current_time = time.time()
        active = []
        for node in self._nodes.values():
            if node.state == NodeState.OFFLINE:
                continue
            if current_time - node.last_heartbeat > self._offline_threshold_seconds:
                # Node has timed out, mark as offline implicitly
                logger.warning(f"Node {node.id} timed out. Marking offline.")
                # We update the dictionary entry with a new offline state
                self._nodes[node.id] = FederationNode(
                    id=node.id,
                    name=node.name,
                    type=node.type,
                    capabilities=node.capabilities,
                    state=NodeState.OFFLINE,
                    last_heartbeat=node.last_heartbeat
                )
            else:
                active.append(node)
        return active
