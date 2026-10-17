import threading
import time

from core.tasks import TaskManager, TaskStatus

from .executor import ExecutionEngine
from .models import ExecutionContext
from .pool import WorkerPool
from .timeouts import TimeoutEnforcer


class TaskDispatcher:
    """Daemon thread bridging the TaskManager queue and the WorkerPool."""
    
    def __init__(
        self,
        task_manager: TaskManager,
        pool: WorkerPool,
        timeout_enforcer: TimeoutEnforcer,
        engine: ExecutionEngine,
    ):
        self._task_manager = task_manager
        self._pool = pool
        self._timeout_enforcer = timeout_enforcer
        self._engine = engine
        
        self._stop = threading.Event()
        self._dispatch_lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._dispatch_loop, name="Task-Dispatcher", daemon=True)
        self._thread.start()

    def stop(self):
        # Serialize shutdown with the status-transition/assignment critical section.
        with self._dispatch_lock:
            self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _requeue_unassigned(self, task) -> None:
        """Return a dequeued task to the queue if no worker accepted it."""
        self._task_manager._queue.enqueue(task)

    def _dispatch_loop(self):
        while not self._stop.is_set():
            # 1. Fetch next READY task. Blocks for up to 1 second to allow clean shutdown checks.
            task = self._task_manager._queue.dequeue()
            
            if not task:
                time.sleep(0.1)
                continue
                
            if self._stop.is_set():
                self._requeue_unassigned(task)
                break

            # 2. Block until a worker is available (Backpressure handling).
            worker = None
            while worker is None and not self._stop.is_set():
                worker = self._pool.acquire_idle_worker()
                if not worker:
                    time.sleep(0.05)

            if not worker:
                # dequeue() already removed this task. Never lose it merely because
                # shutdown won the race while the dispatcher was waiting for capacity.
                self._requeue_unassigned(task)
                break

            # 3. Make shutdown mutually exclusive with transition + assignment.
            with self._dispatch_lock:
                if self._stop.is_set():
                    self._requeue_unassigned(task)
                    break
                running_task = self._task_manager.transition_task(
                    task.task_id.value, TaskStatus.RUNNING
                )
                effective_timeout = self._engine.timeout_for_task(
                    running_task, running_task.timeout_seconds
                )
                if effective_timeout != running_task.timeout_seconds:
                    running_task = running_task.copy(timeout_seconds=effective_timeout)
                context = ExecutionContext(task=running_task)
                self._timeout_enforcer.track(running_task.task_id.value, context)
                try:
                    worker.assign(context)
                except Exception:
                    self._timeout_enforcer.untrack(running_task.task_id.value)
                    self._task_manager.fail(running_task.task_id.value)
                    raise
