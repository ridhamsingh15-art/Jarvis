"""
Federation Synchronization.

Ensures intelligent delta updates for World Model, Memory, and Experience.
"""
import logging
import time
from typing import Any
from .models import SyncPayload
from .transport import TransportLayer
from .registry import NodeRegistry

logger = logging.getLogger(__name__)

class StateSynchronizer:
    """Synchronizes state across the federation."""

    def __init__(self, local_node_id: str, registry: NodeRegistry, transport: TransportLayer):
        self._local_node_id = local_node_id
        self._registry = registry
        self._transport = transport

    def queue_world_model_sync(self, delta: dict[str, Any]) -> None:
        """Queue a partial World Model update."""
        logger.info("Queuing World Model synchronization.")
        payload = SyncPayload(
            source_node_id=self._local_node_id,
            state_type="world_model",
            delta=delta,
            timestamp=time.time()
        )
        self._broadcast(payload)

    def queue_memory_sync(self, delta: dict[str, Any]) -> None:
        """Queue a partial Memory update."""
        logger.info("Queuing Memory synchronization.")
        payload = SyncPayload(
            source_node_id=self._local_node_id,
            state_type="memory",
            delta=delta,
            timestamp=time.time()
        )
        self._broadcast(payload)

    def queue_experience_sync(self, delta: dict[str, Any]) -> None:
        """Queue an Experience Engine update."""
        logger.info("Queuing Experience synchronization.")
        payload = SyncPayload(
            source_node_id=self._local_node_id,
            state_type="experience",
            delta=delta,
            timestamp=time.time()
        )
        self._broadcast(payload)

    def _broadcast(self, payload: SyncPayload) -> None:
        active_nodes = self._registry.get_active_nodes()
        if not active_nodes:
            logger.debug("No active remote nodes to sync with.")
            return
        self._transport.broadcast_sync(active_nodes, payload)
