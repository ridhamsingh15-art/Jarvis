import threading
from typing import List, Optional, Callable, Dict

from core.models import ExecutionResult
from .enums import WorkerStatus
from .worker import WorkerThread
from .models import ExecutionContext

class WorkerPool:
    """Manages a dynamic pool of WorkerThreads scaling bounded queues safely."""
    
    def __init__(self, name: str, min_workers: int, max_workers: int, execute_callback: Callable, completion_callback: Callable):
        self._name = name
        self._min = min_workers
        self._max = max_workers
        self._execute = execute_callback
        self._completion = completion_callback
        
        self._workers: List[WorkerThread] = []
        self._lock = threading.Lock()
        
        # Pre-warm minimum workers
        for i in range(self._min):
            self._spawn_worker()
            
    def _spawn_worker(self) -> Optional[WorkerThread]:
        """Spawns a new worker if under the maximum cap."""
        with self._lock:
            if len(self._workers) >= self._max:
                return None
            worker = WorkerThread(
                name=f"{self._name}-Worker-{len(self._workers)+1}",
                execution_callback=self._execute,
                on_completion=self._completion
            )
            self._workers.append(worker)
            worker.start()
            return worker

    def acquire_idle_worker(self) -> Optional[WorkerThread]:
        """Returns an IDLE worker, or spawns a new one if permitted."""
        with self._lock:
            for w in self._workers:
                if w.status == WorkerStatus.IDLE:
                    return w
                    
        # No idle workers, attempt scale up
        return self._spawn_worker()

    def shutdown(self) -> None:
        """Gracefully stops all workers."""
        with self._lock:
            for w in self._workers:
                w.stop()
            # We don't join immediately to prevent blocking, they will die cleanly as Daemons.
            self._workers.clear()
            
    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            busy = sum(1 for w in self._workers if w.status == WorkerStatus.BUSY)
            return {
                "total_workers": len(self._workers),
                "busy_workers": busy,
                "idle_workers": len(self._workers) - busy
            }
