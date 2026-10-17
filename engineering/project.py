from dataclasses import dataclass, field
from enum import StrEnum


class ProjectPhase(StrEnum):
    REQUIREMENTS = "REQUIREMENTS"
    ARCHITECTURE = "ARCHITECTURE"
    IMPLEMENTATION = "IMPLEMENTATION"
    TESTING = "TESTING"
    REVIEW = "REVIEW"
    DOCUMENTATION = "DOCUMENTATION"
    RELEASE = "RELEASE"
    DEPLOYMENT = "DEPLOYMENT"

@dataclass
class ProjectState:
    id: str
    objective: str
    phase: ProjectPhase = ProjectPhase.REQUIREMENTS
    artifacts: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
