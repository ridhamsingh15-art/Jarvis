import threading

from .exceptions import TaskNotFoundError
from .interfaces import TaskRepository
from .models import Task


class InMemoryTaskRepository(TaskRepository):
    """Thread-safe in-memory storage for Tasks."""
    
    def __init__(self):
        self._store: dict[str, Task] = {}
        self._lock = threading.Lock()
        
    def save(self, task: Task) -> Task:
        with self._lock:
            self._store[task.task_id.value] = task
            return task
            
    def get(self, task_id: str) -> Task:
        with self._lock:
            if task_id not in self._store:
                raise TaskNotFoundError(f"Task '{task_id}' not found.")
            return self._store[task_id]
            
    def list(self) -> list[Task]:
        with self._lock:
            return list(self._store.values())
            
    def delete(self, task_id: str) -> None:
        with self._lock:
            if task_id not in self._store:
                raise TaskNotFoundError(f"Task '{task_id}' not found.")
            del self._store[task_id]
            
    def exists(self, task_id: str) -> bool:
        with self._lock:
            return task_id in self._store
