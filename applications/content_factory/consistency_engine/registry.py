"""
Registry for consistency profiles.
"""

import threading
from typing import Dict, List, Optional
from collections import defaultdict

from .models import CharacterProfile, EnvironmentProfile, ObjectProfile
from .exceptions import ProfileNotFoundError


class ConsistencyRegistry:
    """
    In-memory thread-safe registry for managing project-specific consistency profiles.
    
    In a full production implementation, this would sync to the ProjectBundle's metadata
    or a dedicated database. For this sprint, we maintain the index in memory.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        
        # Maps project_id -> { profile_id -> CharacterProfile }
        self._characters: Dict[str, Dict[str, CharacterProfile]] = defaultdict(dict)
        self._environments: Dict[str, Dict[str, EnvironmentProfile]] = defaultdict(dict)
        self._objects: Dict[str, Dict[str, ObjectProfile]] = defaultdict(dict)

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

    def list_characters(self, project_id: str) -> List[CharacterProfile]:
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

    def list_environments(self, project_id: str) -> List[EnvironmentProfile]:
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

    def list_objects(self, project_id: str) -> List[ObjectProfile]:
        with self._lock:
            return list(self._objects[project_id].values())
