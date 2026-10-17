import time

import pytest

from core.events import EventBus
from core.executor import ExecutorManager
from core.models import Identifier
from core.tasks import (
    Task,
    TaskManager,
    TaskStatus,
)


@pytest.fixture
def manager():
    class MockLogger:
        def error(self, msg, **kwargs): pass
        def info(self, msg, **kwargs): pass
        def debug(self, msg, **kwargs): pass
        
    bus = EventBus(logger=MockLogger())
    # Use a real dict for registry so we can mock TaskRepository
    class MockRepo:
        def __init__(self): self.db = {}
        def save(self, t): self.db[t.task_id.value] = t; return t
        def get(self, tid): return self.db[tid]
        
    tm = TaskManager(MockRepo(), bus)
    
    em = ExecutorManager(bus, tm, min_workers=2, max_workers=5)
    
    # Register some mock actions
    def fast_action(context, **kwargs):
        return {"done": True}
        
    def slow_action(context, **kwargs):
        time.sleep(0.5)
        return {"done": True}
        
    def error_action(context, **kwargs):
        raise ValueError("Simulated panic")
        
    def infinite_action(context, **kwargs):
        while not context.token.is_cancelled:
            time.sleep(0.1)
        return {"cancelled": True}
        
    em.register_action("fast", fast_action)
    em.register_action("slow", slow_action)
    em.register_action("error", error_action)
    em.register_action("infinite", infinite_action)
    
    import asyncio
    asyncio.run(em.start())
    yield em, tm
    asyncio.run(em.stop())


def test_successful_execution(manager):
    _em, tm = manager
    task = Task(task_id=Identifier("t1"), action="fast")
    tm.create(task)
    tm.queue(task.task_id.value)
    
    # Dispatcher should pick it up and execute it
    time.sleep(0.2)
    
    t_final = tm.get(task.task_id.value)
    assert t_final.status == TaskStatus.COMPLETED

def test_failure_isolation(manager):
    em, tm = manager
    task = Task(task_id=Identifier("t2"), action="error")
    tm.create(task)
    tm.queue(task.task_id.value)
    
    time.sleep(0.2)
    
    t_final = tm.get(task.task_id.value)
    assert t_final.status == TaskStatus.FAILED
    
    # Verify pool survived
    assert em._pool.get_stats()["total_workers"] >= 2

def test_timeout_enforcement(manager):
    _em, tm = manager
    # Create task with 0.5s timeout, but action takes infinite
    task = Task(task_id=Identifier("t3"), action="infinite", timeout_seconds=0.5)
    
    tm.create(task)
    tm.queue(task.task_id.value)
    
    time.sleep(0.2)
    assert tm.get(task.task_id.value).status == TaskStatus.RUNNING # Still processing conceptually
    
    # Wait for timeout
    time.sleep(1.5)
    
    t_final = tm.get(task.task_id.value)
    assert t_final.status == TaskStatus.FAILED

def test_worker_scaling(manager):
    em, tm = manager
    
    # Pool starts at 2
    assert em._pool.get_stats()["total_workers"] == 2
    
    # Submit 5 slow tasks simultaneously
    for i in range(5):
        task = Task(task_id=Identifier(f"scale_{i}"), action="slow")
        tm.create(task)
        tm.queue(task.task_id.value)
        
    time.sleep(0.3)
    
    # Pool should have scaled up to 5 to handle parallel load
    assert em._pool.get_stats()["total_workers"] == 5
    
    time.sleep(0.6)
    
    # All should finish
    for i in range(5):
        assert tm.get(f"scale_{i}").status == TaskStatus.COMPLETED
