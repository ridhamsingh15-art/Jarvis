import threading


class CancellationToken:
    """Thread-safe cancellation token for cooperative task cancellation."""
    
    def __init__(self):
        self._cancelled = False
        self._lock = threading.Lock()
        
    @property
    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled
            
    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
