import builtins

from core.models.primitives import Identifier

from .enums import SkillType
from .interfaces import SkillRepository
from .models import Skill


class SkillRegistry:
    """Registry for managing skills, delegating persistence to a repository."""

    def __init__(self, repository: SkillRepository) -> None:
        self._repository = repository

    def register_builtin(self, skill: Skill) -> None:
        """Register a built-in skill."""
        # Ensure the skill type is BUILTIN
        if skill.skill_type != SkillType.BUILTIN:
            skill = Skill(
                id=skill.id,
                name=skill.name,
                description=skill.description,
                version=skill.version,
                skill_type=SkillType.BUILTIN,
                status=skill.status,
                workflow_id=skill.workflow_id,
                required_tools=skill.required_tools,
                required_permissions=skill.required_permissions,
                tags=skill.tags,
                metadata=skill.metadata
            )
        self._repository.register(skill)

    def register(self, skill: Skill) -> None:
        """Register a new skill."""
        self._repository.register(skill)

    def update(self, skill: Skill) -> None:
        """Update an existing skill."""
        self._repository.update(skill)

    def remove(self, skill_id: Identifier) -> bool:
        """Remove a skill by ID."""
        return self._repository.remove(skill_id)

    def get(self, skill_id: Identifier) -> Skill | None:
        """Get a skill by ID."""
        return self._repository.get(skill_id)

    def list(self) -> builtins.list[Skill]:
        """List all registered skills."""
        return self._repository.list()

    def search(
        self,
        id: Identifier | None = None,
        name: str | None = None,
        tags: builtins.list[str] | None = None
    ) -> builtins.list[Skill]:
        """Search for skills by criteria."""
        return self._repository.search(id=id, name=name, tags=tags)
