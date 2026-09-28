"""Protocol defining persistence for learning experiences."""

from typing import Protocol

from core.learning.models import Experience


class ExperienceStore(Protocol):
    """Persistence boundary for future learning backends."""

    def append(self, experience: Experience) -> None: ...
