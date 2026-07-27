from typing import List, Protocol
from .models import Mission

class MissionRepository(Protocol):
    """Interface for Mission storage mechanisms."""
    
    def save(self, mission: Mission) -> Mission:
        """Saves a new or updated mission. Returns the saved mission."""
        ...
        
    def get(self, mission_id: str) -> Mission:
        """Retrieves a mission by ID. Raises MissionNotFoundError if missing."""
        ...
        
    def list(self) -> List[Mission]:
        """Returns a list of all stored missions."""
        ...
        
    def delete(self, mission_id: str) -> None:
        """Deletes a mission by ID. Raises MissionNotFoundError if missing."""
        ...
        
    def exists(self, mission_id: str) -> bool:
        """Returns True if the mission exists."""
        ...
