from dataclasses import dataclass
from typing import Optional
from core.models import JarvisModel

@dataclass(frozen=True, slots=True)
class StartupResult(JarvisModel):
    """Result of the bootstrap sequence."""
    success: bool
    runtime: Optional['Runtime'] = None
    error_message: Optional[str] = None

@dataclass(frozen=True, slots=True)
class ShutdownResult(JarvisModel):
    """Result of the graceful shutdown sequence."""
    success: bool
    error_message: Optional[str] = None
