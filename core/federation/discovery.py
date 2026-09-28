"""
Federation Node Discovery.

Manages the protocol for finding other nodes and advertising this node.
"""
import logging
from typing import Callable
from .models import FederationNode
from .exceptions import DiscoveryError

logger = logging.getLogger(__name__)

class DiscoveryService:
    """Handles network discovery (mDNS / Broadcast stub)."""

    def __init__(self, local_node: FederationNode, on_node_discovered: Callable[[FederationNode], None]):
        self._local_node = local_node
        self._on_node_discovered = on_node_discovered
        self._is_broadcasting = False

    def start_broadcasting(self) -> None:
        """Start advertising the local node to the network."""
        if self._is_broadcasting:
            return
        self._is_broadcasting = True
        logger.info(f"Started broadcasting node {self._local_node.id}")
        # Stub: Normally we'd start a background thread casting UDP/mDNS

    def stop_broadcasting(self) -> None:
        """Stop advertising."""
        self._is_broadcasting = False
        logger.info(f"Stopped broadcasting node {self._local_node.id}")

    def simulate_discovery(self, remote_node: FederationNode) -> None:
        """Simulate receiving a discovery packet from a remote node."""
        if not self._is_broadcasting:
            raise DiscoveryError("Cannot receive discovery events while offline.")
        logger.debug(f"Discovery event: Found {remote_node.id}")
        self._on_node_discovered(remote_node)
