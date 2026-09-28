
import pytest

from core.events import EventBus
from core.models import Identifier
from core.workflows import (
    CyclicDependencyError,
    InMemoryWorkflowRepository,
    InvalidWorkflowTransitionError,
    Workflow,
    WorkflowManager,
    WorkflowNotFoundError,
    WorkflowPriority,
    WorkflowStatus,
    WorkflowValidationError,
    WorkflowValidator,
)


@pytest.fixture
def manager():
    class MockLogger:
        def error(self, msg, **kwargs): pass
        def info(self, msg, **kwargs): pass
        def debug(self, msg, **kwargs): pass
        
    bus = EventBus(logger=MockLogger())
    repo = InMemoryWorkflowRepository()
    return WorkflowManager(repository=repo, event_bus=bus)

def test_workflow_creation(manager):
    wf = Workflow(title="Process Data", mission_id=Identifier("m1"))
    saved = manager.create(wf)
    
    assert saved.status == WorkflowStatus.CREATED
    assert saved.priority == WorkflowPriority.NORMAL
    assert saved.progress == 0.0
    
    fetched = manager.get(saved.workflow_id.value)
    assert fetched.title == "Process Data"
    assert fetched.mission_id.value == "m1"

def test_workflow_valid_transitions(manager):
    wf = manager.create(Workflow())
    w_id = wf.workflow_id.value
    
    ready = manager.ready(w_id)
    assert ready.status == WorkflowStatus.READY
    
    running = manager.resume(w_id)
    assert running.status == WorkflowStatus.RUNNING
    assert running.started_at is not None
    
    paused = manager.pause(w_id)
    assert paused.status == WorkflowStatus.PAUSED
    
    running_again = manager.resume(w_id)
    assert running_again.status == WorkflowStatus.RUNNING
    
    completed = manager.complete(w_id)
    assert completed.status == WorkflowStatus.COMPLETED
    assert completed.completed_at is not None

def test_workflow_invalid_transition(manager):
    wf = manager.create(Workflow())
    w_id = wf.workflow_id.value
    
    # CREATED -> RUNNING is invalid
    with pytest.raises(InvalidWorkflowTransitionError):
        manager.resume(w_id)

def test_workflow_updates(manager):
    wf = manager.create(Workflow())
    w_id = wf.workflow_id.value
    
    updated = manager.update(w_id, progress=50.5)
    assert updated.progress == 50.5
    
    with pytest.raises(ValueError):
        manager.update(w_id, progress=150.0)

def test_graph_and_topological_sort(manager):
    wf = manager.create(Workflow())
    graph = manager.get_graph(wf.workflow_id.value)
    
    # Add tasks T1, T2, T3
    # T3 depends on T2, T2 depends on T1
    graph.add_task("T1")
    graph.add_task("T2")
    graph.add_task("T3")
    
    graph.add_dependency("T2", "T1")
    graph.add_dependency("T3", "T2")
    
    assert graph.detect_cycles() is False
    
    order = graph.topological_sort()
    assert order == ["T1", "T2", "T3"]
    
def test_graph_cyclic_detection(manager):
    wf = manager.create(Workflow())
    graph = manager.get_graph(wf.workflow_id.value)
    
    graph.add_task("A")
    graph.add_task("B")
    graph.add_task("C")
    
    graph.add_dependency("A", "B")
    graph.add_dependency("B", "C")
    graph.add_dependency("C", "A") # Cycle
    
    assert graph.detect_cycles() is True
    
    with pytest.raises(CyclicDependencyError):
        graph.topological_sort()
        
def test_workflow_validator(manager):
    wf = manager.create(Workflow())
    graph = manager.get_graph(wf.workflow_id.value)
    
    graph.add_task("T1")
    graph.add_dependency("T2", "T1") # T2 was added implicitly
    
    # Graph has T1, T2. But let's say the Workflow only knows about T1
    with pytest.raises(WorkflowValidationError):
        WorkflowValidator.validate_graph(graph, task_ids={"T1"})
        
    # Cycle test
    graph.add_dependency("T1", "T2")
    with pytest.raises(CyclicDependencyError):
        WorkflowValidator.validate_graph(graph, task_ids={"T1", "T2"})

def test_repository_errors(manager):
    with pytest.raises(WorkflowNotFoundError):
        manager.get("invalid-id")
        
    with pytest.raises(WorkflowNotFoundError):
        manager.delete("invalid-id")
