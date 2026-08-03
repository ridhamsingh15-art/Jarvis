from dataclasses import dataclass, field

from core.models import JarvisModel

from .enums import EntityType


@dataclass(frozen=True)
class Entity(JarvisModel):
    id: str
    name: str
    type: EntityType
    properties: dict[str, str] = field(default_factory=dict)

@dataclass(frozen=True)
class Relation(JarvisModel):
    source_id: str
    target_id: str
    relation_type: str
    weight: float = 1.0

@dataclass(frozen=True)
class Inference(JarvisModel):
    conclusion: str
    confidence: float
    evidence: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class Hypothesis(JarvisModel):
    id: str
    description: str
    expected_outcome: str

@dataclass(frozen=True)
class SimulationResult(JarvisModel):
    success_probability: float
    execution_time_ms: float
    resource_cost: dict[str, float]
    is_viable: bool
