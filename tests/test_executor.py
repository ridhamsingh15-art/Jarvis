import pytest
import time
import threading

from core.events import EventBus
from core.models import Identifier
from core.tasks import TaskManager, TaskDefinition, TaskStatus, TaskPolicy, TimeoutPolicy

from core.executor import ExecutorManager

@pytest.fixture
def manager():
    class MockLogger:
        def error(self, msg, **kwargs): pass
        def info(self, msg, **kwargs): pass
        def debug(self, msg, **kwargs): pass
        
    bus = EventBus(logger=MockLogger())
    tm = TaskManager(bus)
    
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
    
    em.start()
    yield em, tm
    em.stop()


def test_successful_execution(manager):
    em, tm = manager
    task = TaskDefinition(id=Identifier("t1"), action="fast")
    tm.submit_task(task)
    
    # Dispatcher should pick it up and execute it
    time.sleep(0.2)
    
    t_final = tm.get_task(task.id.value)
    assert t_final.status == TaskStatus.COMPLETED
    assert t_final.result.success is True
    assert t_final.result.output == {"done": True}

def test_failure_isolation(manager):
    em, tm = manager
    task = TaskDefinition(id=Identifier("t2"), action="error")
    tm.submit_task(task)
    
    time.sleep(0.2)
    
    t_final = tm.get_task(task.id.value)
    assert t_final.status == TaskStatus.FAILED
    assert t_final.result.success is False
    assert "Simulated panic" in t_final.result.error_message
    
    # Verify pool survived
    assert em._pool.get_stats()["total_workers"] >= 2

def test_timeout_enforcement(manager):
    em, tm = manager
    # Create task with 0.3s timeout, but action takes infinite
    policy = TaskPolicy(timeout=TimeoutPolicy(deadline_seconds=0.3))
    task = TaskDefinition(id=Identifier("t3"), action="infinite", policy=policy)
    
    tm.submit_task(task)
    
    time.sleep(0.1)
    assert tm.get_task(task.id.value).status == TaskStatus.RUNNING # Still processing conceptually
    
    # Wait for timeout
    time.sleep(1.5)
    
    t_final = tm.get_task(task.id.value)
    assert t_final.status == TaskStatus.FAILED
    assert t_final.result.success is False
    assert "exceeded timeout" in t_final.result.error_message

def test_worker_scaling(manager):
    em, tm = manager
    
    # Pool starts at 2
    assert em._pool.get_stats()["total_workers"] == 2
    
    # Submit 5 slow tasks simultaneously
    for i in range(5):
        task = TaskDefinition(id=Identifier(f"scale_{i}"), action="slow")
        tm.submit_task(task)
        
    time.sleep(0.1)
    
    # Pool should have scaled up to 5 to handle parallel load
    assert em._pool.get_stats()["total_workers"] == 5
    
    time.sleep(0.6)
    
    # All should finish
    for i in range(5):
        assert tm.get_task(f"scale_{i}").status == TaskStatus.COMPLETED
