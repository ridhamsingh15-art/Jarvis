import builtins
import threading
from typing import Any

from core.models.primitives import Identifier

from .interfaces import ExperienceRepository
from .models import Experience


class InMemoryExperienceRepository(ExperienceRepository):
    """Thread-safe, in-memory repository for experiences."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._experiences: dict[str, Experience] = {}

    def save(self, experience: Experience) -> None:
        with self._lock:
            self._experiences[experience.id.value] = experience

    def get(self, experience_id: Identifier) -> Experience | None:
        with self._lock:
            return self._experiences.get(experience_id.value)

    def remove(self, experience_id: Identifier) -> bool:
        with self._lock:
            if experience_id.value in self._experiences:
                del self._experiences[experience_id.value]
                return True
            return False

    def list(self) -> builtins.list[Experience]:
        with self._lock:
            return list(self._experiences.values())

    def find_by_skill(self, skill_id: Identifier) -> builtins.list[Experience]:
        with self._lock:
            return [e for e in self._experiences.values() if e.skill_id and e.skill_id.value == skill_id.value]

    def find_by_workflow(self, workflow_id: Identifier) -> builtins.list[Experience]:
        with self._lock:
            return [e for e in self._experiences.values() if e.workflow_id and e.workflow_id.value == workflow_id.value]

    def find_successful(self) -> builtins.list[Experience]:
        with self._lock:
            return [e for e in self._experiences.values() if e.success]

    def find_failed(self) -> builtins.list[Experience]:
        with self._lock:
            return [e for e in self._experiences.values() if not e.success]

    def statistics(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._experiences)
            successful = sum(1 for e in self._experiences.values() if e.success)
            failed = total - successful
            success_rate = (successful / total) if total > 0 else 0.0
            
            return {
                "total_experiences": total,
                "successful_experiences": successful,
                "failed_experiences": failed,
                "success_rate": success_rate,
            }
