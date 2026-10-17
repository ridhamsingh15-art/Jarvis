import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .base import JarvisModel
from .exceptions import ModelValidationError


@dataclass(frozen=True, slots=True)
class Identifier(JarvisModel):
    """Canonical unique identifier."""
    value: str = field(default_factory=lambda: str(uuid.uuid4()))

    def validate(self) -> None:
        if not self.value or not isinstance(self.value, str):
            raise ModelValidationError("Identifier value must be a non-empty string.")

@dataclass(frozen=True, slots=True)
class Timestamp(JarvisModel):
    """Canonical UTC timestamp."""
    iso_value: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate(self) -> None:
        try:
            datetime.fromisoformat(self.iso_value)
        except (ValueError, TypeError):
            raise ModelValidationError(f"Invalid ISO-8601 timestamp: {self.iso_value}")

@dataclass(frozen=True, slots=True)
class Version(JarvisModel):
    """Semantic Versioning (SemVer) model."""
    major: int = 1
    minor: int = 0
    patch: int = 0
    label: str = ""

    def validate(self) -> None:
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ModelValidationError("Version numbers must be non-negative integers.")
            
    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        return f"{base}-{self.label}" if self.label else base

@dataclass(frozen=True, slots=True)
class Metadata(JarvisModel):
    """Generic bucket for loosely-structured contextual data."""
    tags: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not isinstance(self.tags, dict) or not isinstance(self.annotations, dict):
            raise ModelValidationError("Metadata tags and annotations must be dictionaries.")
