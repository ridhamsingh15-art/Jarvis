"""
JARVIS AIOS Event Bus

The canonical communication backbone ensuring all subsystems remain decoupled,
communicating safely via strongly typed events.
"""

from .interfaces import EventHandler, AsyncEventHandler
from .bus import EventBus

__all__ = [
    "EventHandler", "AsyncEventHandler",
    "EventBus"
]
