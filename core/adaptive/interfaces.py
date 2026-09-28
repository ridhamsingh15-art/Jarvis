import builtins
from abc import ABC, abstractmethod
from typing import Any

from core.models.primitives import Identifier

from .models import (
    Experience,
    LearningPattern,
    LearningRecommendation,
    OptimizationPlan,
)


class ExperienceRepository(ABC):
    """Abstract interface for experience persistence."""
    
    @abstractmethod
    def save(self, experience: Experience) -> None:
        pass

    @abstractmethod
    def get(self, experience_id: Identifier) -> Experience | None:
        pass

    @abstractmethod
    def remove(self, experience_id: Identifier) -> bool:
        pass

    @abstractmethod
    def list(self) -> builtins.list[Experience]:
        pass

    @abstractmethod
    def find_by_skill(self, skill_id: Identifier) -> builtins.list[Experience]:
        pass

    @abstractmethod
    def find_by_workflow(self, workflow_id: Identifier) -> builtins.list[Experience]:
        pass

    @abstractmethod
    def find_successful(self) -> builtins.list[Experience]:
        pass

    @abstractmethod
    def find_failed(self) -> builtins.list[Experience]:
        pass

    @abstractmethod
    def statistics(self) -> dict[str, Any]:
        pass


class ExperienceCollector(ABC):
    """Abstract interface for generating experiences from missions."""
    
    @abstractmethod
    def record_mission(self, user_input: str, success: bool, duration: float, **kwargs: Any) -> Experience:
        pass


class PatternDetector(ABC):
    """Abstract interface for extracting deterministic patterns."""
    
    @abstractmethod
    def detect(self, experiences: list[Experience]) -> list[LearningPattern]:
        pass


class Learner(ABC):
    """Abstract interface for generating recommendations from patterns."""
    
    @abstractmethod
    def learn(self, patterns: list[LearningPattern]) -> list[LearningRecommendation]:
        pass


class Evaluator(ABC):
    """Abstract interface for tracking metrics and confidence."""
    
    @abstractmethod
    def evaluate(self, experiences: list[Experience]) -> dict[str, Any]:
        pass


class Optimizer(ABC):
    """Abstract interface for creating optimization plans."""
    
    @abstractmethod
    def optimize(self, recommendations: list[LearningRecommendation]) -> OptimizationPlan:
        pass
