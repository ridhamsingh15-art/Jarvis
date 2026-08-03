from collections.abc import Awaitable
from typing import Protocol

from core.models import Event


class EventHandler(Protocol):
    """Protocol for synchronous event handlers."""
    def __call__(self, event: Event) -> None:
        ...

class AsyncEventHandler(Protocol):
    """Protocol for asynchronous event handlers."""
    def __call__(self, event: Event) -> Awaitable[None]:
        ...
