"""
Domain service for managing Character Profiles.
"""

from typing import List, Optional
import uuid

from .models import CharacterProfile
from .registry import ConsistencyRegistry
from .validator import ProfileValidator
from .telemetry import ConsistencyTelemetry


class CharacterLibrary:
    """Manages the creation and retrieval of character profiles."""

    def __init__(
        self,
        registry: ConsistencyRegistry,
        validator: ProfileValidator,
        telemetry: ConsistencyTelemetry
    ) -> None:
        self._registry = registry
        self._validator = validator
        self._telemetry = telemetry

    def create_character(self, project_id: str, name: str, description: str, **kwargs) -> CharacterProfile:
        """Creates and registers a new CharacterProfile."""
        profile_id = str(uuid.uuid4())
        profile = CharacterProfile(
            id=profile_id,
            name=name,
            description=description,
            **kwargs
        )
        
        self._validator.validate(profile)
        self._registry.save_character(project_id, profile)
        self._telemetry.emit_profile_registered(project_id, "character", profile.name)
        
        return profile

    def get_character(self, project_id: str, profile_id: str) -> CharacterProfile:
        """Retrieves a CharacterProfile by ID."""
        return self._registry.get_character(project_id, profile_id)

    def search_characters(self, project_id: str, query: str = "") -> List[CharacterProfile]:
        """Searches for characters by name or description (simple text match)."""
        all_chars = self._registry.list_characters(project_id)
        if not query:
            return all_chars
            
        q = query.lower()
        return [c for c in all_chars if q in c.name.lower() or q in c.description.lower()]
