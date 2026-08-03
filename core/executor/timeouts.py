import threading
import time
from datetime import datetime

from .models import ExecutionContext


class TimeoutEnforcer:
    """Daemon thread tracking active contexts against their TimeoutPolicy."""
    
    def __init__(self):
        self._active: dict[str, ExecutionContext] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        
    def track(self, task_id: str, context: ExecutionContext):
        # We only track tasks with a timeout > 0
        if context.task.timeout_seconds and context.task.timeout_seconds > 0:
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
                    start = datetime.fromisoformat(ctx.task.updated_at.iso_value).timestamp() if ctx.task.updated_at else now # Approximate start timestamp
                    limit = ctx.task.timeout_seconds or 0
                    
                    if limit > 0 and (now - start) > limit:
                        # Timeout breached!
                        ctx.token.cancel()
                        del self._active[task_id]
                        
            # Sleep 1 second before checking again
            time.sleep(1.0)
