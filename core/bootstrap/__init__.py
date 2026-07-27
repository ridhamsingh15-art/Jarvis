"""
JARVIS AIOS Bootstrap

The canonical startup and shutdown orchestrator, tying together the Foundation
layer into an orchestratable Runtime.
"""

from .models import StartupResult, ShutdownResult
from .runtime import Runtime
from .lifecycle import LifecycleManager
from .bootstrapper import Bootstrap

__all__ = [
    "StartupResult", "ShutdownResult",
    "Runtime", "LifecycleManager", "Bootstrap"
]
