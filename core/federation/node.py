"""
Local Node representation.

Encapsulates the current machine's capabilities and manages the heartbeat.
"""
import logging
import time
from .models import FederationNode, NodeCapabilities, NodeType, NodeState

logger = logging.getLogger(__name__)

class LocalNode:
    """Represents the local JARVIS instance in the federation."""

    def __init__(self, name: str, node_type: NodeType):
        self._name = name
        self._node_type = node_type
        self._capabilities = self._detect_capabilities()
        self._state = NodeState.ONLINE
        
        self._node_model = FederationNode(
            name=self._name,
            type=self._node_type,
            capabilities=self._capabilities,
            state=self._state,
            last_heartbeat=time.time()
        )
        logger.info(f"Initialized Local Node: {self._node_model.id} ({self._name})")

    def _detect_capabilities(self) -> NodeCapabilities:
        """Detect hardware and software capabilities of the local machine."""
        # In a real implementation, this would use psutil, GPUtil, etc.
        # Stub implementation for now.
        return NodeCapabilities(
            cpu_cores=8,
            gpu_available=True if self._node_type in (NodeType.SERVER, NodeType.DESKTOP) else False,
            memory_gb=16.0,
            storage_available_gb=500.0,
            installed_models=["gpt-4", "stable-diffusion-xl"],
            installed_plugins=["filesystem", "shell"],
            installed_apps=["content_factory", "software_engineer"]
        )

    def get_node_model(self) -> FederationNode:
        """Get the immutable model representation of this node."""
        return self._node_model

    def update_state(self, new_state: NodeState) -> None:
        """Update the local node's state."""
        self._state = new_state
        self._node_model = FederationNode(
            id=self._node_model.id,
            name=self._node_model.name,
            type=self._node_model.type,
            capabilities=self._node_model.capabilities,
            state=self._state,
            last_heartbeat=time.time()
        )
        logger.debug(f"Local node state updated to {self._state.value}")

    def generate_heartbeat(self) -> FederationNode:
        """Generate a fresh heartbeat model for broadcasting."""
        self._node_model = FederationNode(
            id=self._node_model.id,
            name=self._node_model.name,
            type=self._node_model.type,
            capabilities=self._node_model.capabilities,
            state=self._state,
            last_heartbeat=time.time()
        )
        return self._node_model
