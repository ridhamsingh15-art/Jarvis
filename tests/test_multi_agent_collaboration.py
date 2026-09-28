import pytest
from unittest.mock import MagicMock
from core.models.primitives import Identifier
from core.reasoning.execution_plan import ExecutionPlan
from core.agents.manager import AgentManager
from core.agents.registry import DefaultAgentRegistry
from core.agents.coordinator import MasterCoordinator
from core.agents.lifecycle import AgentLifecycleAdapter
from core.agents.models import SharedContext
from core.agents.content_agents import WriterAgent, StoryboardAgent, VisualDirectorAgent
from core.agents.shared_memory import ThreadSafeSharedMemory
from core.agents.voting import VotingEngine
from core.events.bus import EventBus

@pytest.fixture
def registry():
    return DefaultAgentRegistry()

@pytest.fixture
def lifecycle():
    mission_manager = MagicMock()
    return AgentLifecycleAdapter(mission_manager)

@pytest.fixture
def coordinator(registry, lifecycle):
    return MasterCoordinator(registry, lifecycle)

@pytest.fixture
def manager(registry, coordinator):
    logger = MagicMock()
    event_bus = EventBus(logger)
    return AgentManager(
        registry=registry,
        coordinator=coordinator,
        shared_memory=ThreadSafeSharedMemory(),
        voting_engine=VotingEngine(),
        event_bus=event_bus,
        logger=logger
    )

@pytest.mark.asyncio
async def test_content_factory_collaboration(manager, registry):
    # Register agents
    registry.register(WriterAgent())
    registry.register(StoryboardAgent())
    registry.register(VisualDirectorAgent())
    
    # Create an execution plan requiring these three steps sequentially
    plan = ExecutionPlan(
        ordered_steps=[
            "Write the script",
            "Generate storyboard from script",
            "Generate visual images from storyboard"
        ]
    )
    
    initial_context = SharedContext(
        session_id=Identifier("test_session"),
        read_only_data={"initial_prompt": "Make a video about AI"}
    )
    
    results = await manager.execute_plan(plan, Identifier("parent_mission_1"), initial_context)
    
    # Verify we got 3 successful results
    assert len(results) == 3
    for r in results:
        assert r.status == "COMPLETED"
        
    # Verify the accumulated context output in the final payload
    # (The master coordinator merges outputs dynamically step by step)
    assert "script" in results[0].payload
    assert "storyboard" in results[1].payload
    assert "images" in results[2].payload
