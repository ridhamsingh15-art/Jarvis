"""
JARVIS AIOS Event Bus

The canonical communication backbone ensuring all subsystems remain decoupled,
communicating safely via strongly typed events.
"""

from .bus import EventBus
from .interfaces import AsyncEventHandler, EventHandler

__all__ = [
    "AsyncEventHandler",
    "EventBus",
    "EventHandler"
]
