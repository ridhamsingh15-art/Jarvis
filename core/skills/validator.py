from collections.abc import Callable

from core.models.primitives import Identifier

from .exceptions import SkillValidationError
from .interfaces import SkillRepository, SkillValidator
from .models import Skill


class DefaultSkillValidator(SkillValidator):
    """Default implementation for skill validation."""

    def __init__(
        self,
        repository: SkillRepository,
        workflow_checker: Callable[[Identifier], bool] | None = None
    ) -> None:
        self._repository = repository
        self._workflow_checker = workflow_checker

    def validate(self, skill: Skill) -> None:
        if not skill.name or not skill.name.strip():
            raise SkillValidationError("Skill name cannot be empty.")
            
        # Semantic version is validated by the Version primitive itself,
        # but we can ensure it's not None.
        if skill.version is None:
            raise SkillValidationError("Skill version cannot be None.")
            
        if skill.workflow_id is not None and self._workflow_checker and not self._workflow_checker(skill.workflow_id):
            raise SkillValidationError(f"Workflow '{skill.workflow_id.value}' does not exist.")
                
        if len(skill.tags) != len(set(skill.tags)):
            raise SkillValidationError("Skill tags must not contain duplicates.")
            
        for tool in skill.required_tools:
            if not tool or not tool.strip():
                raise SkillValidationError("Required tool names cannot be empty.")
                
        # To avoid race conditions, repository handles actual uniqueness on insert,
        # but we can do a preliminary check here if we want to fail fast for new skills.
        # Since 'validate' might be called on update, we shouldn't strictly fail 
        # if the ID exists unless we know it's a creation event, but the repository 
        # already raises DuplicateSkillError.
