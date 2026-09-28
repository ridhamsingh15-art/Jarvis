"""
Domain service for managing Object Profiles.
"""

from typing import List
import uuid

from .models import ObjectProfile
from .registry import ConsistencyRegistry
from .validator import ProfileValidator
from .telemetry import ConsistencyTelemetry


class ObjectLibrary:
    """Manages the creation and retrieval of object/prop profiles."""

    def __init__(
        self,
        registry: ConsistencyRegistry,
        validator: ProfileValidator,
        telemetry: ConsistencyTelemetry
    ) -> None:
        self._registry = registry
        self._validator = validator
        self._telemetry = telemetry

    def create_object(self, project_id: str, name: str, description: str, **kwargs) -> ObjectProfile:
        """Creates and registers a new ObjectProfile."""
        profile_id = str(uuid.uuid4())
        profile = ObjectProfile(
            id=profile_id,
            name=name,
            description=description,
            **kwargs
        )
        
        self._validator.validate(profile)
        self._registry.save_object(project_id, profile)
        self._telemetry.emit_profile_registered(project_id, "object", profile.name)
        
        return profile

    def get_object(self, project_id: str, profile_id: str) -> ObjectProfile:
        """Retrieves an ObjectProfile by ID."""
        return self._registry.get_object(project_id, profile_id)

    def search_objects(self, project_id: str, query: str = "") -> List[ObjectProfile]:
        """Searches for objects by name or description."""
        all_objs = self._registry.list_objects(project_id)
        if not query:
            return all_objs
            
        q = query.lower()
        return [o for o in all_objs if q in o.name.lower() or q in o.description.lower()]
