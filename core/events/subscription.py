import uuid
from dataclasses import dataclass, field
from typing import Callable, Union, Awaitable
import re

from core.models import Event
from .interfaces import EventHandler, AsyncEventHandler

@dataclass
class Subscription:
    """Represents a bound handler to a specific topic pattern."""
    topic_pattern: str
    handler: Union[EventHandler, AsyncEventHandler]
    priority: int = 0
    once_only: bool = False
    
    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    _regex: re.Pattern = field(init=False)

    def __post_init__(self):
        # Convert topic pattern to regex
        # e.g., system.* -> ^system\.[^\.]+$
        # e.g., system.** -> ^system\..*$
        
        escaped = re.escape(self.topic_pattern)
        # Replace escaped wildcards with regex equivalents
        escaped = escaped.replace(r"\*\*", r".*")
        escaped = escaped.replace(r"\*", r"[^\.]+")
        
        self._regex = re.compile(f"^{escaped}$")

    def matches(self, topic: str) -> bool:
        """Evaluates if this subscription matches the given event topic."""
        return self._regex.match(topic) is not None
