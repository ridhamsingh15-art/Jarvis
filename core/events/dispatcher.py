import asyncio
import inspect
from typing import List, Callable

from core.models import Event
from core.telemetry import AsyncLogger
from core.errors import InternalError

from .registry import HandlerRegistry

class EventDispatcher:
    """
    Executes handlers for an event, isolating failures safely.
    """
    def __init__(self, registry: HandlerRegistry, logger: AsyncLogger):
        self._registry = registry
        self._logger = logger

    async def dispatch_async(self, event: Event) -> None:
        """
        Dispatches an event asynchronously.
        Sync handlers are run in the thread pool to avoid blocking.
        """
        subs = self._registry.get_matching_subscriptions(event.topic)
        
        for sub in subs:
            if sub.once_only:
                self._registry.unsubscribe(sub.subscription_id)
                
            try:
                if inspect.iscoroutinefunction(sub.handler):
                    await sub.handler(event)
                else:
                    # Offload sync handler to thread pool
                    await asyncio.to_thread(sub.handler, event)
            except Exception as e:
                self._handle_fault(e, sub.subscription_id, event)

    def dispatch_sync(self, event: Event) -> None:
        """
        Dispatches an event synchronously.
        Async handlers will be executed using a new event loop if none exists,
        or run_until_complete if we can safely grab the current one.
        """
        subs = self._registry.get_matching_subscriptions(event.topic)
        
        for sub in subs:
            if sub.once_only:
                self._registry.unsubscribe(sub.subscription_id)
                
            try:
                if inspect.iscoroutinefunction(sub.handler):
                    self._run_async_sync(sub.handler, event)
                else:
                    sub.handler(event)
            except Exception as e:
                self._handle_fault(e, sub.subscription_id, event)

    def _run_async_sync(self, handler, event: Event) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
            
        if loop and loop.is_running():
            # If we are already inside a running loop, create a task
            # (Note: this makes it 'fire and forget' in a sync context, which is 
            # generally discouraged, but necessary if bridging sync->async without blocking)
            loop.create_task(handler(event))
        else:
            asyncio.run(handler(event))

    def _handle_fault(self, exc: Exception, subscription_id: str, event: Event) -> None:
        """Safely isolate and log handler panics."""
        wrapped = InternalError(
            message=f"Event handler failed for subscription {subscription_id} on topic {event.topic}",
            root_cause=exc,
            metadata={"event_id": event.id.value, "topic": event.topic}
        )
        
        self._logger.error(
            message="Event Dispatch Failure",
            error=wrapped.to_dict()
        )
