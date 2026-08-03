import time

import pytest

from core.events import EventBus
from core.models import Identifier
from core.tasks import Task, TaskManager


# We need a mock WorkflowManager
class MockWorkflowManager:
    def submit_workflow(self, w): pass
    def start_workflow(self, w_id): pass

from core.scheduler import (
    DelayedTrigger,
    ExponentialBackoff,
    ImmediateTrigger,
    IntervalTrigger,
    LinearBackoff,
    SchedulerManager,
)


@pytest.fixture
def manager():
    class MockLogger:
        def error(self, msg, **kwargs): pass
        def info(self, msg, **kwargs): pass
        def debug(self, msg, **kwargs): pass
        
    bus = EventBus(logger=MockLogger())
    from core.tasks.repository import InMemoryTaskRepository
    tm = TaskManager(InMemoryTaskRepository(), bus)
    wm = MockWorkflowManager()
    
    sm = SchedulerManager(bus, tm, wm)
    import asyncio
    asyncio.run(sm.start())
    yield sm
    asyncio.run(sm.stop())

def test_immediate_scheduling(manager):
    task = Task(task_id=Identifier("t1"))
    
    # Schedule
    manager.schedule_task(task, ImmediateTrigger())
    
    # Wait for TimerLoop to process it
    time.sleep(0.1)
    
    # Should be pushed to task manager
    assert manager._task_manager._queue.size() == 1

def test_delayed_scheduling(manager):
    task = Task(task_id=Identifier("t2"))
    
    manager.schedule_task(task, DelayedTrigger(0.2))
    
    # Right away, it shouldn't be in the TaskManager
    time.sleep(0.05)
    assert manager._task_manager._queue.size() == 0
    
    # Wait until it fires
    time.sleep(0.3)
    assert manager._task_manager._queue.size() == 1

def test_queue_priority_ordering():
    from core.scheduler import ScheduledJob, SchedulerQueue
    
    q = SchedulerQueue()
    j1 = ScheduledJob(next_execution_time=time.time() + 10.0)
    j2 = ScheduledJob(next_execution_time=time.time() + 1.0)
    j3 = ScheduledJob(next_execution_time=time.time() + 5.0)
    
    q.enqueue(j1)
    q.enqueue(j2)
    q.enqueue(j3)
    
    assert q.dequeue().next_execution_time == j2.next_execution_time
    assert q.dequeue().next_execution_time == j3.next_execution_time
    assert q.dequeue().next_execution_time == j1.next_execution_time

def test_interval_scheduling(manager):
    task = Task(task_id=Identifier("t3"))
    
    # Fire 3 times, every 0.1s
    manager.schedule_task(task, IntervalTrigger(0.1, max_fires=3))
    
    time.sleep(0.4)
    
    # Should be pushed 3 times
    assert manager._task_manager._queue.size() == 3
    # Scheduler queue should be empty because it finished max_fires
    assert manager._engine._queue.size() == 0

def test_cancellation(manager):
    task = Task(task_id=Identifier("t4"))
    
    job_id = manager.schedule_task(task, DelayedTrigger(0.5))
    
    time.sleep(0.1)
    assert manager._engine._queue.size() == 1
    
    success = manager.cancel_schedule(job_id)
    assert success is True
    assert manager._engine._queue.size() == 0
    
    time.sleep(0.5)
    # Should not have fired
    assert manager._task_manager._queue.size() == 0

def test_backoff_policies():
    lin = LinearBackoff(base_delay=2.0)
    assert lin.next_delay(1) == 2.0
    assert lin.next_delay(2) == 4.0
    
    exp = ExponentialBackoff(base_delay=1.0, factor=2.0)
    assert exp.next_delay(1) == 1.0
    assert exp.next_delay(2) == 2.0
    assert exp.next_delay(3) == 4.0
