"""
Registry for consistency profiles.
"""

import threading
from collections import defaultdict

from .exceptions import ProfileNotFoundError
from .models import CharacterProfile, EnvironmentProfile, ObjectProfile


class ConsistencyRegistry:
    """
    In-memory thread-safe registry for managing project-specific consistency profiles.
    
    In a full production implementation, this would sync to the ProjectBundle's metadata
    or a dedicated database. For this sprint, we maintain the index in memory.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        
        # Maps project_id -> { profile_id -> CharacterProfile }
        self._characters: dict[str, dict[str, CharacterProfile]] = defaultdict(dict)
        self._environments: dict[str, dict[str, EnvironmentProfile]] = defaultdict(dict)
        self._objects: dict[str, dict[str, ObjectProfile]] = defaultdict(dict)

    # --- Character Registry ---
    def save_character(self, project_id: str, profile: CharacterProfile) -> None:
        with self._lock:
            self._characters[project_id][profile.id] = profile

    def get_character(self, project_id: str, profile_id: str) -> CharacterProfile:
        with self._lock:
            profile = self._characters[project_id].get(profile_id)
            if not profile:
                raise ProfileNotFoundError("Character", profile_id)
            return profile

    def list_characters(self, project_id: str) -> list[CharacterProfile]:
        with self._lock:
            return list(self._characters[project_id].values())

    # --- Environment Registry ---
    def save_environment(self, project_id: str, profile: EnvironmentProfile) -> None:
        with self._lock:
            self._environments[project_id][profile.id] = profile

    def get_environment(self, project_id: str, profile_id: str) -> EnvironmentProfile:
        with self._lock:
            profile = self._environments[project_id].get(profile_id)
            if not profile:
                raise ProfileNotFoundError("Environment", profile_id)
            return profile

    def list_environments(self, project_id: str) -> list[EnvironmentProfile]:
        with self._lock:
            return list(self._environments[project_id].values())

    # --- Object Registry ---
    def save_object(self, project_id: str, profile: ObjectProfile) -> None:
        with self._lock:
            self._objects[project_id][profile.id] = profile

    def get_object(self, project_id: str, profile_id: str) -> ObjectProfile:
        with self._lock:
            profile = self._objects[project_id].get(profile_id)
            if not profile:
                raise ProfileNotFoundError("Object", profile_id)
            return profile

    def list_objects(self, project_id: str) -> list[ObjectProfile]:
        with self._lock:
            return list(self._objects[project_id].values())
