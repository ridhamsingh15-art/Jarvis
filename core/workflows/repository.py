import threading
from typing import Dict, List

from .models import Workflow
from .interfaces import WorkflowRepository
from .exceptions import WorkflowNotFoundError

class InMemoryWorkflowRepository(WorkflowRepository):
    """Thread-safe in-memory storage for Workflows."""
    
    def __init__(self):
        self._store: Dict[str, Workflow] = {}
        self._lock = threading.Lock()
        
    def save(self, workflow: Workflow) -> Workflow:
        with self._lock:
            self._store[workflow.workflow_id.value] = workflow
            return workflow
            
    def get(self, workflow_id: str) -> Workflow:
        with self._lock:
            if workflow_id not in self._store:
                raise WorkflowNotFoundError(f"Workflow '{workflow_id}' not found.")
            return self._store[workflow_id]
            
    def list(self) -> List[Workflow]:
        with self._lock:
            return list(self._store.values())
            
    def delete(self, workflow_id: str) -> None:
        with self._lock:
            if workflow_id not in self._store:
                raise WorkflowNotFoundError(f"Workflow '{workflow_id}' not found.")
            del self._store[workflow_id]
            
    def exists(self, workflow_id: str) -> bool:
        with self._lock:
            return workflow_id in self._store
