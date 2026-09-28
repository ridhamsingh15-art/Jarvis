"""
Validators for consistency profiles.
"""

from typing import Union
from .models import CharacterProfile, EnvironmentProfile, ObjectProfile
from .exceptions import ConsistencyValidationError


class ProfileValidator:
    """Validates the structural integrity of consistency profiles."""

    def validate_character(self, profile: CharacterProfile) -> None:
        """Validates a CharacterProfile."""
        if not profile.name or not profile.name.strip():
            raise ConsistencyValidationError(f"CharacterProfile {profile.id} is missing a name.")
        if not profile.description or not profile.description.strip():
            raise ConsistencyValidationError(f"CharacterProfile {profile.id} '{profile.name}' is missing a description.")

    def validate_environment(self, profile: EnvironmentProfile) -> None:
        """Validates an EnvironmentProfile."""
        if not profile.name or not profile.name.strip():
            raise ConsistencyValidationError(f"EnvironmentProfile {profile.id} is missing a name.")
        if not profile.description or not profile.description.strip():
            raise ConsistencyValidationError(f"EnvironmentProfile {profile.id} '{profile.name}' is missing a description.")

    def validate_object(self, profile: ObjectProfile) -> None:
        """Validates an ObjectProfile."""
        if not profile.name or not profile.name.strip():
            raise ConsistencyValidationError(f"ObjectProfile {profile.id} is missing a name.")
        if not profile.description or not profile.description.strip():
            raise ConsistencyValidationError(f"ObjectProfile {profile.id} '{profile.name}' is missing a description.")

    def validate(self, profile: Union[CharacterProfile, EnvironmentProfile, ObjectProfile]) -> None:
        """Validates any profile type."""
        if isinstance(profile, CharacterProfile):
            self.validate_character(profile)
        elif isinstance(profile, EnvironmentProfile):
            self.validate_environment(profile)
        elif isinstance(profile, ObjectProfile):
            self.validate_object(profile)
        else:
            raise ConsistencyValidationError(f"Unknown profile type: {type(profile)}")
