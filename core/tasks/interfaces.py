from typing import List, Protocol
from .models import Task

class TaskRepository(Protocol):
    """Interface for Task storage mechanisms."""
    
    def save(self, task: Task) -> Task:
        """Saves a new or updated task. Returns the saved task."""
        ...
        
    def get(self, task_id: str) -> Task:
        """Retrieves a task by ID. Raises TaskNotFoundError if missing."""
        ...
        
    def list(self) -> List[Task]:
        """Returns a list of all stored tasks."""
        ...
        
    def delete(self, task_id: str) -> None:
        """Deletes a task by ID. Raises TaskNotFoundError if missing."""
        ...
        
    def exists(self, task_id: str) -> bool:
        """Returns True if the task exists."""
        ...
