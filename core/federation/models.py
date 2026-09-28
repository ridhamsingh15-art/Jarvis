"""
Data models for the Federation subsystem.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional


class NodeType(StrEnum):
    DESKTOP = "desktop"
    LAPTOP = "laptop"
    SERVER = "server"
    CLOUD_WORKER = "cloud_worker"
    MOBILE = "mobile"


class NodeState(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    SYNCING = "syncing"


@dataclass(frozen=True, kw_only=True)
class NodeCapabilities:
    """Hardware and software capabilities of a node."""
    cpu_cores: int
    gpu_available: bool
    memory_gb: float
    storage_available_gb: float
    installed_models: list[str] = field(default_factory=list)
    installed_plugins: list[str] = field(default_factory=list)
    installed_apps: list[str] = field(default_factory=list)

    def meets_requirements(self, required_gpu: bool, min_memory: float) -> bool:
        """Helper to determine if capabilities meet minimum requirements."""
        if required_gpu and not self.gpu_available:
            return False
        if self.memory_gb < min_memory:
            return False
        return True


@dataclass(frozen=True, kw_only=True)
class FederationNode:
    """Representation of a trusted node in the federation."""
    id: str = field(default_factory=lambda: f"node_{uuid.uuid4().hex[:8]}")
    name: str
    type: NodeType
    capabilities: NodeCapabilities
    state: NodeState = NodeState.ONLINE
    last_heartbeat: float = 0.0


@dataclass(frozen=True, kw_only=True)
class FederatedMission:
    """A mission payload meant to be executed on a remote node."""
    mission_id: str
    target_node_id: str
    payload: dict[str, Any]
    required_gpu: bool = False
    min_memory_gb: float = 1.0


@dataclass(frozen=True, kw_only=True)
class SyncPayload:
    """A payload for synchronizing World Model or Memory state."""
    source_node_id: str
    state_type: str # 'world_model', 'memory', 'experience'
    delta: dict[str, Any]
    timestamp: float
