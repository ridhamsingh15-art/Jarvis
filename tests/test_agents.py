from unittest.mock import MagicMock

import pytest

from core.agents import (
    AgentManager,
    AgentTask,
    CodingAgent,
    ConsensusStrategy,
    DefaultAgentRegistry,
    MasterCoordinator,
    PlannerAgent,
    SharedContext,
    TaskState,
    ThreadSafeSharedMemory,
    Vote,
    VoteType,
    VotingEngine,
)
from core.events.bus import EventBus
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState


@pytest.fixture
def registry():
    return DefaultAgentRegistry()

@pytest.fixture
def shared_memory():
    return ThreadSafeSharedMemory()

@pytest.fixture
def voting_engine():
    return VotingEngine()

@pytest.fixture
def coordinator(registry):
    return MasterCoordinator(registry)

@pytest.fixture
def manager(registry, coordinator, shared_memory, voting_engine):
    logger = MagicMock()
    event_bus = EventBus(logger)
    return AgentManager(
        registry=registry,
        coordinator=coordinator,
        shared_memory=shared_memory,
        voting_engine=voting_engine,
        event_bus=event_bus,
        logger=logger
    )

def test_registry(registry):
    planner = PlannerAgent()
    registry.register(planner)
    assert registry.get_agent(planner.profile.id) == planner
    
    agents = registry.get_agents_by_capability("planning")
    assert len(agents) == 1
    assert agents[0] == planner

def test_shared_memory(shared_memory):
    shared_memory.write("test_key", {"data": 123})
    assert shared_memory.read("test_key") == {"data": 123}
    
    # Verify isolation
    shared_memory.read("test_key")["data"] = 456
    assert shared_memory.read("test_key") == {"data": 123}

def test_voting_engine(voting_engine):
    votes = [
        Vote(agent_id=Identifier("a1"), decision=VoteType.APPROVE),
        Vote(agent_id=Identifier("a2"), decision=VoteType.REJECT),
        Vote(agent_id=Identifier("a3"), decision=VoteType.APPROVE)
    ]
    
    res = voting_engine.evaluate(votes, ConsensusStrategy.MAJORITY)
    assert res is not None
    assert res.decision == VoteType.APPROVE

@pytest.mark.asyncio
async def test_coordinator_assign(manager, registry):
    planner = PlannerAgent()
    registry.register(planner)
    
    result = await manager.assign("Can you plan my day?", {})
    assert result.status == TaskState.COMPLETED
    assert "plan" in result.payload

@pytest.mark.asyncio
async def test_parallel_execution(manager):
    planner = PlannerAgent()
    coder = CodingAgent()
    
    tasks = [
        AgentTask(id=Identifier("t1"), intent="Plan something"),
        AgentTask(id=Identifier("t2"), intent="Code something")
    ]
    
    context = SharedContext(session_id=Identifier("s1"))
    
    results = await manager.execute([planner, coder], tasks, context)
    
    assert len(results) == 2
    assert results[0].status == TaskState.COMPLETED
    assert results[1].status == TaskState.COMPLETED

@pytest.mark.asyncio
async def test_manager_lifecycle(manager):
    assert manager.state == ComponentState.INITIALIZED
    await manager.start()
    assert manager.state == ComponentState.RUNNING
    await manager.stop()
    assert manager.state == ComponentState.STOPPED
