import threading
from collections import deque

from .models import Task


class TaskQueue:
    """A thread-safe FIFO task queue. Never executes tasks itself."""
    
    def __init__(self):
        self._queue: deque[Task] = deque()
        self._lock = threading.Lock()
        
    def enqueue(self, task: Task) -> None:
        with self._lock:
            self._queue.append(task)
            
    def dequeue(self) -> Task | None:
        with self._lock:
            if self._queue:
                return self._queue.popleft()
            return None
            
    def peek(self) -> Task | None:
        with self._lock:
            if self._queue:
                return self._queue[0]
            return None
            
    def is_empty(self) -> bool:
        with self._lock:
            return len(self._queue) == 0
            
    def size(self) -> int:
        with self._lock:
            return len(self._queue)
