"""Learning extension facade; records experiences without changing planning."""

from core.learning.experience import ExperienceStore
from core.learning.models import Experience


class LearningManager:
    """Optional, dependency-injected recorder for future optimization."""

    def __init__(self, store: ExperienceStore) -> None:
        self._store = store

    def record(self, experience: Experience) -> None:
        """Persist an execution experience through the configured store."""
        self._store.append(experience)
