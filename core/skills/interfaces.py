import builtins
from abc import ABC, abstractmethod

from core.models.primitives import Identifier

from .models import Skill, SkillMatch


class SkillRepository(ABC):
    """Abstract interface for skill persistence."""
    
    @abstractmethod
    def register(self, skill: Skill) -> None:
        """Register a new skill."""

    @abstractmethod
    def remove(self, skill_id: Identifier) -> bool:
        """Remove a skill by ID."""

    @abstractmethod
    def update(self, skill: Skill) -> None:
        """Update an existing skill."""

    @abstractmethod
    def get(self, skill_id: Identifier) -> Skill | None:
        """Get a skill by ID."""

    @abstractmethod
    def exists(self, skill_id: Identifier) -> bool:
        """Check if a skill exists."""

    @abstractmethod
    def list(self) -> builtins.list[Skill]:
        """List all registered skills."""

    @abstractmethod
    def search(
        self,
        id: Identifier | None = None,
        name: str | None = None,
        tags: builtins.list[str] | None = None
    ) -> builtins.list[Skill]:
        """Search for skills by optional criteria."""


class SkillMatcher(ABC):
    """Abstract interface for matching queries to skills."""
    
    @abstractmethod
    def match(self, query: str, skills: builtins.list[Skill]) -> builtins.list[SkillMatch]:
        """
        Match a query against a list of candidate skills.
        Returns a list of SkillMatch sorted by score descending.
        """


class SkillValidator(ABC):
    """Abstract interface for skill validation rules."""
    
    @abstractmethod
    def validate(self, skill: Skill) -> None:
        """
        Validate a skill against constraints.
        Raises SkillValidationError if invalid.
        """
