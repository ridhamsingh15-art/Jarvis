import builtins
import threading

from core.models.primitives import Identifier

from .exceptions import DuplicateSkillError, SkillNotFoundError
from .interfaces import SkillRepository
from .models import Skill


class InMemorySkillRepository(SkillRepository):
    """Thread-safe, in-memory repository for skills."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._skills: dict[str, Skill] = {}
        self._name_index: dict[str, str] = {}

    def register(self, skill: Skill) -> None:
        with self._lock:
            if skill.id.value in self._skills:
                raise DuplicateSkillError(f"Skill with ID '{skill.id.value}' already exists.")
            if skill.name in self._name_index:
                raise DuplicateSkillError(f"Skill with name '{skill.name}' already exists.")
            
            self._skills[skill.id.value] = skill
            self._name_index[skill.name] = skill.id.value

    def remove(self, skill_id: Identifier) -> bool:
        with self._lock:
            if skill_id.value in self._skills:
                skill = self._skills.pop(skill_id.value)
                self._name_index.pop(skill.name, None)
                return True
            return False

    def update(self, skill: Skill) -> None:
        with self._lock:
            if skill.id.value not in self._skills:
                raise SkillNotFoundError(f"Skill with ID '{skill.id.value}' not found.")
            
            old_skill = self._skills[skill.id.value]
            if old_skill.name != skill.name:
                if skill.name in self._name_index:
                    raise DuplicateSkillError(f"Skill with name '{skill.name}' already exists.")
                self._name_index.pop(old_skill.name, None)
                self._name_index[skill.name] = skill.id.value
            
            self._skills[skill.id.value] = skill

    def get(self, skill_id: Identifier) -> Skill | None:
        with self._lock:
            return self._skills.get(skill_id.value)

    def exists(self, skill_id: Identifier) -> bool:
        with self._lock:
            return skill_id.value in self._skills

    def list(self) -> builtins.list[Skill]:
        with self._lock:
            return list(self._skills.values())

    def search(
        self,
        id: Identifier | None = None,
        name: str | None = None,
        tags: builtins.list[str] | None = None
    ) -> builtins.list[Skill]:
        with self._lock:
            results = list(self._skills.values())
            
            if id is not None:
                results = [s for s in results if s.id.value == id.value]
            
            if name is not None:
                results = [s for s in results if s.name == name]
                
            if tags:
                tag_set = set(tags)
                results = [s for s in results if tag_set.issubset(set(s.tags))]
                
            return results
