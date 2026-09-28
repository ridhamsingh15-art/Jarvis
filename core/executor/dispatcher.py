import threading
import time

from core.tasks import TaskManager, TaskStatus

from .models import ExecutionContext
from .pool import WorkerPool
from .timeouts import TimeoutEnforcer


class TaskDispatcher:
    """Daemon thread bridging the TaskManager queue and the WorkerPool."""
    
    def __init__(self, task_manager: TaskManager, pool: WorkerPool, timeout_enforcer: TimeoutEnforcer):
        self._task_manager = task_manager
        self._pool = pool
        self._timeout_enforcer = timeout_enforcer
        
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._dispatch_loop, name="Task-Dispatcher", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _dispatch_loop(self):
        while not self._stop.is_set():
            # 1. Fetch next READY task. Blocks for up to 1 second to allow clean shutdown checks.
            task = self._task_manager._queue.dequeue()
            
            if not task:
                time.sleep(0.1)
                continue
                
            if self._stop.is_set():
                break
                
            # 2. Block until a worker is available (Backpressure handling)
            worker = None
            while worker is None and not self._stop.is_set():
                worker = self._pool.acquire_idle_worker()
                if not worker:
                    time.sleep(0.05) # Wait for a busy worker to free up
                    
            if not worker:
                break # We stopped while waiting for a worker
                
            # 3. Transition to RUNNING, build context and assign
            running_task = self._task_manager.transition_task(task.task_id.value, TaskStatus.RUNNING)
            context = ExecutionContext(task=running_task)
            self._timeout_enforcer.track(running_task.task_id.value, context)
            worker.assign(context)
