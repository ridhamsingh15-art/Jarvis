import threading

from .exceptions import MissionNotFoundError
from .interfaces import MissionRepository
from .models import Mission


class InMemoryMissionRepository(MissionRepository):
    """Thread-safe in-memory storage for Missions."""
    
    def __init__(self):
        self._store: dict[str, Mission] = {}
        self._lock = threading.Lock()
        
    def save(self, mission: Mission) -> Mission:
        with self._lock:
            self._store[mission.mission_id.value] = mission
            return mission
            
    def get(self, mission_id: str) -> Mission:
        with self._lock:
            if mission_id not in self._store:
                raise MissionNotFoundError(f"Mission '{mission_id}' not found.")
            return self._store[mission_id]
            
    def list(self) -> list[Mission]:
        with self._lock:
            return list(self._store.values())
            
    def delete(self, mission_id: str) -> None:
        with self._lock:
            if mission_id not in self._store:
                raise MissionNotFoundError(f"Mission '{mission_id}' not found.")
            del self._store[mission_id]
            
    def exists(self, mission_id: str) -> bool:
        with self._lock:
            return mission_id in self._store
