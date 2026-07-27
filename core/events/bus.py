from typing import Union

from core.models import Event
from core.telemetry import AsyncLogger

from .interfaces import EventHandler, AsyncEventHandler
from .registry import HandlerRegistry
from .dispatcher import EventDispatcher


class EventBus:
    """
    The canonical communication backbone for JARVIS AIOS.
    """
    def __init__(self, logger: AsyncLogger):
        self._registry = HandlerRegistry()
        self._dispatcher = EventDispatcher(self._registry, logger)
        self._logger = logger

    def subscribe(
        self, 
        topic_pattern: str, 
        handler: Union[EventHandler, AsyncEventHandler], 
        priority: int = 0, 
        once_only: bool = False
    ) -> str:
        """
        Subscribes a handler to a topic pattern.
        """
        return self._registry.subscribe(topic_pattern, handler, priority, once_only)

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Removes a subscription.
        """
        return self._registry.unsubscribe(subscription_id)

    def publish(self, event: Event) -> None:
        """
        Publishes an event synchronously.
        """
        self._dispatcher.dispatch_sync(event)

    async def publish_async(self, event: Event) -> None:
        """
        Publishes an event asynchronously.
        """
        await self._dispatcher.dispatch_async(event)

    def shutdown(self) -> None:
        """
        Cleans up the event bus.
        """
        self._registry._subscriptions.clear()
