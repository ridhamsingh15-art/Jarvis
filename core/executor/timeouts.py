import threading
import time
from typing import Dict

from core.tasks import CancellationToken
from .models import ExecutionContext

class TimeoutEnforcer:
    """Daemon thread tracking active contexts against their TimeoutPolicy."""
    
    def __init__(self):
        self._active: Dict[str, ExecutionContext] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
    def track(self, task_id: str, context: ExecutionContext):
        # We only track tasks with a timeout > 0
        if context.task.policy and context.task.policy.timeout and context.task.policy.timeout.deadline_seconds > 0:
            with self._lock:
                self._active[task_id] = context
                
    def untrack(self, task_id: str):
        with self._lock:
            self._active.pop(task_id, None)
            
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._enforce_loop, name="Timeout-Enforcer", daemon=True)
        self._thread.start()
        
    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            
    def _enforce_loop(self):
        while not self._stop.is_set():
            now = time.time()
            with self._lock:
                for task_id, ctx in list(self._active.items()):
                    start = ctx.task.updated_at # Approximate start timestamp
                    limit = ctx.task.policy.timeout.deadline_seconds
                    
                    if now - start > limit:
                        # Timeout breached!
                        ctx.token.cancel(reason=f"Execution exceeded timeout of {limit} seconds")
                        del self._active[task_id]
                        
            # Sleep 1 second before checking again
            time.sleep(1.0)
