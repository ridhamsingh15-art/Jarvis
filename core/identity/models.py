"""
Identity domain models.

Immutable, frozen dataclasses following the established JarvisModel pattern.
"""

from dataclasses import dataclass, field

from core.models.base import JarvisModel


@dataclass(frozen=True, slots=True)
class PersonaTrait(JarvisModel):
    """A single personality trait that defines JARVIS behaviour."""

    name: str
    description: str


@dataclass(frozen=True, slots=True)
class BehaviouralRule(JarvisModel):
    """A behavioural constraint governing JARVIS responses."""

    rule: str
    priority: int = 0


@dataclass(frozen=True, slots=True)
class GuardrailPattern(JarvisModel):
    """A pattern-replacement pair for post-processing LLM output."""

    pattern: str
    replacement: str
    description: str


@dataclass(frozen=True, slots=True)
class IdentityContext(JarvisModel):
    """Aggregated runtime context for prompt construction."""

    identity_statement: str
    traits: tuple[PersonaTrait, ...] = field(default_factory=tuple)
    rules: tuple[BehaviouralRule, ...] = field(default_factory=tuple)
    active_model: str = "unknown"
    active_provider: str = "unknown"
