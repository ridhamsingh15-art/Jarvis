import threading
from typing import List, Dict, Union

from .subscription import Subscription
from .interfaces import EventHandler, AsyncEventHandler

class HandlerRegistry:
    """
    Thread-safe registry managing pub/sub subscriptions.
    """
    def __init__(self):
        self._subscriptions: List[Subscription] = []
        self._lock = threading.Lock()

    def subscribe(
        self, 
        topic_pattern: str, 
        handler: Union[EventHandler, AsyncEventHandler], 
        priority: int = 0, 
        once_only: bool = False
    ) -> str:
        """
        Registers a new handler.
        Returns the subscription_id.
        """
        sub = Subscription(
            topic_pattern=topic_pattern,
            handler=handler,
            priority=priority,
            once_only=once_only
        )
        
        with self._lock:
            self._subscriptions.append(sub)
            # Sort immediately so resolution is fast (highest priority first)
            self._subscriptions.sort(key=lambda s: s.priority, reverse=True)
            
        return sub.subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Removes a subscription by ID.
        Returns True if removed, False if not found.
        """
        with self._lock:
            for i, sub in enumerate(self._subscriptions):
                if sub.subscription_id == subscription_id:
                    self._subscriptions.pop(i)
                    return True
        return False

    def get_matching_subscriptions(self, topic: str) -> List[Subscription]:
        """
        Returns a priority-ordered list of subscriptions matching the topic.
        """
        with self._lock:
            # We copy the list to prevent mutation during iteration
            return [sub for sub in self._subscriptions if sub.matches(topic)]
