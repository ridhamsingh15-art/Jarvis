"""
Tests for the Federation subsystem.
"""
import pytest
import time
from core.federation.models import NodeType, NodeCapabilities, FederationNode, FederatedMission, NodeState
from core.federation.node import LocalNode
from core.federation.registry import NodeRegistry
from core.federation.scheduler import FederationScheduler
from core.federation.security import SecurityManager
from core.federation.exceptions import DelegationFailedError, FederationAuthError

class TestLocalNode:
    def test_node_initialization(self):
        node = LocalNode(name="TestDesktop", node_type=NodeType.DESKTOP)
        model = node.get_node_model()
        assert model.name == "TestDesktop"
        assert model.type == NodeType.DESKTOP
        assert model.state == NodeState.ONLINE

class TestNodeRegistry:
    def test_register_and_retrieve(self):
        registry = NodeRegistry()
        node = FederationNode(
            name="RemoteServer",
            type=NodeType.SERVER,
            capabilities=NodeCapabilities(cpu_cores=32, gpu_available=True, memory_gb=128.0, storage_available_gb=1000.0),
            last_heartbeat=time.time()
        )
        registry.register_or_update(node)
        
        retrieved = registry.get_node(node.id)
        assert retrieved is not None
        assert retrieved.name == "RemoteServer"
        
        active = registry.get_active_nodes()
        assert len(active) == 1

class TestFederationScheduler:
    def test_schedule_mission_success(self):
        registry = NodeRegistry()
        # Add a low-spec node
        registry.register_or_update(FederationNode(
            name="Laptop",
            type=NodeType.LAPTOP,
            capabilities=NodeCapabilities(cpu_cores=4, gpu_available=False, memory_gb=8.0, storage_available_gb=100.0),
            last_heartbeat=time.time()
        ))
        # Add a high-spec node
        server_node = FederationNode(
            name="GPU-Server",
            type=NodeType.SERVER,
            capabilities=NodeCapabilities(cpu_cores=32, gpu_available=True, memory_gb=128.0, storage_available_gb=1000.0),
            last_heartbeat=time.time()
        )
        registry.register_or_update(server_node)
        
        scheduler = FederationScheduler(registry)
        
        # Mission requires GPU
        mission = FederatedMission(mission_id="m1", target_node_id="", payload={}, required_gpu=True, min_memory_gb=16.0)
        
        assigned = scheduler.schedule_mission(mission)
        assert assigned.name == "GPU-Server"

    def test_schedule_mission_failure(self):
        registry = NodeRegistry()
        registry.register_or_update(FederationNode(
            name="Laptop",
            type=NodeType.LAPTOP,
            capabilities=NodeCapabilities(cpu_cores=4, gpu_available=False, memory_gb=8.0, storage_available_gb=100.0),
            last_heartbeat=time.time()
        ))
        
        scheduler = FederationScheduler(registry)
        mission = FederatedMission(mission_id="m1", target_node_id="", payload={}, required_gpu=True, min_memory_gb=16.0)
        
        with pytest.raises(DelegationFailedError):
            scheduler.schedule_mission(mission)

class TestSecurityManager:
    def test_authentication(self):
        security = SecurityManager()
        node = FederationNode(
            name="Remote",
            type=NodeType.SERVER,
            capabilities=NodeCapabilities(cpu_cores=4, gpu_available=False, memory_gb=8.0, storage_available_gb=100.0)
        )
        
        # Should pass
        security.authenticate_node(node, "known-trusted-cluster-key-12345")
        
        # Should fail
        with pytest.raises(FederationAuthError):
            security.authenticate_node(node, "invalid-key")
