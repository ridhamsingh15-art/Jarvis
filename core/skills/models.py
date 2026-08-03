from dataclasses import dataclass, field

from core.models import JarvisModel
from core.models.primitives import Identifier, Metadata, Timestamp, Version

from .enums import SkillStatus, SkillType


@dataclass(frozen=True, slots=True)
class Skill(JarvisModel):
    """Immutable representation of a JARVIS AIOS Skill."""
    name: str
    description: str
    skill_type: SkillType
    id: Identifier = field(default_factory=Identifier)
    version: Version = field(default_factory=Version)
    status: SkillStatus = SkillStatus.ACTIVE
    workflow_id: Identifier | None = None
    required_tools: list[str] = field(default_factory=list)
    required_permissions: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: Metadata = field(default_factory=Metadata)


@dataclass(frozen=True, slots=True)
class SkillMatch(JarvisModel):
    """Result of matching a query against a skill."""
    skill: Skill
    score: float
    reason: str


@dataclass(frozen=True, slots=True)
class SkillExecution(JarvisModel):
    """Execution metadata and outcome for a skill run."""
    skill_id: Identifier
    started_at: Timestamp
    finished_at: Timestamp
    duration: float
    success: bool
    metadata: Metadata = field(default_factory=Metadata)
