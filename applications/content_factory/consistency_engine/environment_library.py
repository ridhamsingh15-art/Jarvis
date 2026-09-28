"""
Domain service for managing Environment Profiles.
"""

from typing import List
import uuid

from .models import EnvironmentProfile
from .registry import ConsistencyRegistry
from .validator import ProfileValidator
from .telemetry import ConsistencyTelemetry


class EnvironmentLibrary:
    """Manages the creation and retrieval of environment profiles."""

    def __init__(
        self,
        registry: ConsistencyRegistry,
        validator: ProfileValidator,
        telemetry: ConsistencyTelemetry
    ) -> None:
        self._registry = registry
        self._validator = validator
        self._telemetry = telemetry

    def create_environment(self, project_id: str, name: str, description: str, **kwargs) -> EnvironmentProfile:
        """Creates and registers a new EnvironmentProfile."""
        profile_id = str(uuid.uuid4())
        profile = EnvironmentProfile(
            id=profile_id,
            name=name,
            description=description,
            **kwargs
        )
        
        self._validator.validate(profile)
        self._registry.save_environment(project_id, profile)
        self._telemetry.emit_profile_registered(project_id, "environment", profile.name)
        
        return profile

    def get_environment(self, project_id: str, profile_id: str) -> EnvironmentProfile:
        """Retrieves an EnvironmentProfile by ID."""
        return self._registry.get_environment(project_id, profile_id)

    def search_environments(self, project_id: str, query: str = "") -> List[EnvironmentProfile]:
        """Searches for environments by name or description."""
        all_envs = self._registry.list_environments(project_id)
        if not query:
            return all_envs
            
        q = query.lower()
        return [e for e in all_envs if q in e.name.lower() or q in e.description.lower()]
