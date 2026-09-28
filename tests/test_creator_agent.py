import pytest
from unittest.mock import MagicMock
from core.models.primitives import Identifier
from core.creator import (
    CreatorManager,
    CreatorObjective,
    ObjectiveParser,
    GraphBuilder,
    WorkflowCompiler,
    RecoveryManager,
    ProgressTracker,
    WorkflowNode,
    ProductionState,
    WorkflowResolutionError
)

@pytest.fixture
def mock_llm_client():
    return MagicMock()

@pytest.fixture
def mock_project_manager():
    pm = MagicMock()
    mock_project = MagicMock()
    mock_project.id = Identifier("test_project_1")
    mock_project.name = "Test Project"
    pm.create_project.return_value = mock_project
    pm.get_project.return_value = mock_project
    return pm

@pytest.fixture
def mock_mission_manager():
    mm = MagicMock()
    mm._repository = MagicMock()
    return mm

@pytest.fixture
def mock_agent_manager():
    am = MagicMock()
    return am

@pytest.fixture
def creator_manager(mock_llm_client, mock_project_manager, mock_mission_manager, mock_agent_manager):
    return CreatorManager(
        llm_client=mock_llm_client,
        project_manager=mock_project_manager,
        mission_manager=mock_mission_manager,
        agent_manager=mock_agent_manager
    )

def test_objective_parser(mock_llm_client):
    parser = ObjectiveParser(mock_llm_client)
    obj = parser.parse("Create today's Ramayana episode")
    
    assert obj.topic == "Ramayana"
    assert obj.target_format == "video"
    assert "script_writing" in obj.required_capabilities

def test_dependency_graph():
    builder = GraphBuilder()
    obj = CreatorObjective(
        id=Identifier("test_obj"),
        raw_prompt="Test video",
        target_format="video",
        topic="Testing",
        required_capabilities=["script_writing", "storyboarding", "image_generation"]
    )
    
    graph = builder.build(obj)
    
    assert "script" in graph.nodes
    assert "storyboard" in graph.nodes
    assert "images" in graph.nodes
    
    assert "script" in graph.nodes["storyboard"].dependencies
    assert "storyboard" in graph.nodes["images"].dependencies
    
def test_dependency_graph_cycle():
    graph = GraphBuilder().build(CreatorObjective(Identifier("t"), "", "", ""))
    graph.add_node(WorkflowNode(id="a", capability="", description=""))
    graph.add_node(WorkflowNode(id="b", capability="", description=""))
    graph.add_dependency("a", "b")
    graph.add_dependency("b", "a")
    
    with pytest.raises(WorkflowResolutionError):
        GraphBuilder()._validate_graph(graph)

def test_workflow_compilation():
    builder = GraphBuilder()
    compiler = WorkflowCompiler()
    
    obj = CreatorObjective(
        id=Identifier("test_obj"),
        raw_prompt="Test video",
        target_format="video",
        topic="Testing",
        required_capabilities=["script_writing", "storyboarding", "image_generation"]
    )
    
    graph = builder.build(obj)
    sequence = compiler.compile(graph)
    
    assert len(sequence) == 3
    # script must be before storyboard
    script_idx = next(i for i, n in enumerate(sequence) if n.id == "script")
    storyboard_idx = next(i for i, n in enumerate(sequence) if n.id == "storyboard")
    assert script_idx < storyboard_idx

def test_recovery_manager():
    recovery = RecoveryManager()
    sequence = [
        WorkflowNode(id="script", capability="", description=""),
        WorkflowNode(id="storyboard", capability="", description="")
    ]
    
    recovered = recovery.resume_from_checkpoint(sequence, ["script"])
    assert recovered[0].state == ProductionState.SKIPPED
    assert recovered[1].state == ProductionState.PENDING
    
    runnable = recovery.filter_runnable_sequence(recovered)
    assert len(runnable) == 1
    assert runnable[0].id == "storyboard"

def test_progress_tracker():
    sequence = [
        WorkflowNode(id="script", capability="", description=""),
        WorkflowNode(id="storyboard", capability="", description="")
    ]
    
    tracker = ProgressTracker("mission_1", sequence)
    report = tracker.generate_report()
    assert report.overall_progress_percent == 0.0
    
    sequence[0].state = ProductionState.COMPLETED
    report = tracker.generate_report()
    assert report.overall_progress_percent == 50.0

@pytest.mark.asyncio
async def test_creator_manager_orchestration(creator_manager, mock_agent_manager):
    from unittest.mock import AsyncMock
    # Setup mock to return dummy AgentResults for 9 stages
    from core.agents.models import AgentResult
    from core.agents.enums import TaskState
    from core.models.primitives import Timestamp
    
    dummy_results = [
        AgentResult(task_id=Identifier(f"t_{i}"), status=TaskState.COMPLETED, timestamp=Timestamp())
        for i in range(9)
    ]
    mock_agent_manager.execute_plan = AsyncMock(return_value=dummy_results)
    
    report = await creator_manager.create_production("Create today's Ramayana episode")
    
    assert report.overall_progress_percent == 100.0
    assert len(report.completed_stages) == 9
    creator_manager._project_manager.create_project.assert_called_once()
    creator_manager._mission_manager._repository.save.assert_called_once()
