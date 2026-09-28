
import pytest

from core.events import EventBus
from core.models import Identifier
from core.tasks import (
    InMemoryTaskRepository,
    InvalidTaskTransitionError,
    Task,
    TaskManager,
    TaskNotFoundError,
    TaskPriority,
    TaskStatus,
    TaskValidationError,
)


@pytest.fixture
def manager():
    class MockLogger:
        def error(self, msg, **kwargs): pass
        def info(self, msg, **kwargs): pass
        def debug(self, msg, **kwargs): pass
        
    bus = EventBus(logger=MockLogger())
    repo = InMemoryTaskRepository()
    return TaskManager(repository=repo, event_bus=bus)

def test_task_creation(manager):
    task = Task(title="Extract Data", workflow_id=Identifier("w1"))
    saved = manager.create(task)
    
    assert saved.status == TaskStatus.CREATED
    assert saved.priority == TaskPriority.NORMAL
    assert saved.progress == 0.0
    
    fetched = manager.get(saved.task_id.value)
    assert fetched.title == "Extract Data"
    assert fetched.workflow_id.value == "w1"

def test_task_valid_transitions(manager):
    task = manager.create(Task())
    t_id = task.task_id.value
    
    blocked = manager.block(t_id)
    assert blocked.status == TaskStatus.BLOCKED
    
    ready = manager.ready(t_id)
    assert ready.status == TaskStatus.READY
    
    queued = manager.queue(t_id)
    assert queued.status == TaskStatus.QUEUED
    
    running = manager.resume(t_id)
    assert running.status == TaskStatus.RUNNING
    assert running.started_at is not None
    
    paused = manager.pause(t_id)
    assert paused.status == TaskStatus.PAUSED
    
    running_again = manager.resume(t_id)
    assert running_again.status == TaskStatus.RUNNING
    
    completed = manager.complete(t_id)
    assert completed.status == TaskStatus.COMPLETED
    assert completed.completed_at is not None

def test_task_invalid_transition(manager):
    task = manager.create(Task())
    t_id = task.task_id.value
    
    # CREATED -> RUNNING is invalid
    with pytest.raises(InvalidTaskTransitionError):
        manager.resume(t_id)

def test_task_updates(manager):
    task = manager.create(Task())
    t_id = task.task_id.value
    
    updated = manager.update(t_id, progress=50.5)
    assert updated.progress == 50.5
    
    with pytest.raises(ValueError):
        manager.update(t_id, progress=150.0)

def test_task_validation_errors(manager):
    # max_retries < 0
    with pytest.raises(TaskValidationError):
        manager.create(Task(max_retries=-1))
        
    # retry_count > max_retries
    with pytest.raises(TaskValidationError):
        manager.create(Task(max_retries=3, retry_count=4))
        
    # timeout_seconds <= 0
    with pytest.raises(TaskValidationError):
        manager.create(Task(timeout_seconds=0))
        
def test_task_queue(manager):
    assert manager._queue.is_empty() is True
    
    t1 = manager.create(Task(title="T1"))
    t2 = manager.create(Task(title="T2"))
    
    manager.ready(t1.task_id.value)
    manager.ready(t2.task_id.value)
    
    manager.queue(t1.task_id.value)
    manager.queue(t2.task_id.value)
    
    assert manager._queue.size() == 2
    assert manager._queue.is_empty() is False
    assert manager._queue.peek().title == "T1"
    
    popped1 = manager._queue.dequeue()
    assert popped1.title == "T1"
    assert manager._queue.size() == 1
    
    popped2 = manager._queue.dequeue()
    assert popped2.title == "T2"
    assert manager._queue.size() == 0
    
    assert manager._queue.dequeue() is None

def test_repository_errors(manager):
    with pytest.raises(TaskNotFoundError):
        manager.get("invalid-id")
        
    with pytest.raises(TaskNotFoundError):
        manager.delete("invalid-id")
