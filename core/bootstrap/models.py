from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from core.models import JarvisModel

if TYPE_CHECKING:
    from core.bootstrap.runtime import Runtime


@dataclass(frozen=True, slots=True)
class StartupResult(JarvisModel):
    """Result of the bootstrap sequence."""
    success: bool
    runtime: Optional['Runtime'] = None
    error_message: str | None = None

@dataclass(frozen=True, slots=True)
class ShutdownResult(JarvisModel):
    """Result of the graceful shutdown sequence."""
    success: bool
    error_message: str | None = None
