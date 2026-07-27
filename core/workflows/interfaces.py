from typing import List, Protocol
from .models import Workflow

class WorkflowRepository(Protocol):
    """Interface for Workflow storage mechanisms."""
    
    def save(self, workflow: Workflow) -> Workflow:
        """Saves a new or updated workflow. Returns the saved workflow."""
        ...
        
    def get(self, workflow_id: str) -> Workflow:
        """Retrieves a workflow by ID. Raises WorkflowNotFoundError if missing."""
        ...
        
    def list(self) -> List[Workflow]:
        """Returns a list of all stored workflows."""
        ...
        
    def delete(self, workflow_id: str) -> None:
        """Deletes a workflow by ID. Raises WorkflowNotFoundError if missing."""
        ...
        
    def exists(self, workflow_id: str) -> bool:
        """Returns True if the workflow exists."""
        ...
