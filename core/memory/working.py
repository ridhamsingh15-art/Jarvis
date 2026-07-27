import time
import threading
from typing import Optional, Any, Dict, List

from core.models import Identifier, Timestamp, Event
from core.events import EventBus
from .enums import MemoryType
from .models import WorkingMemoryItem
from .interfaces import StorageProvider, MemoryRepository
from .exceptions import MemoryNotFoundError

class WorkingMemoryRepository(MemoryRepository):
    """Repository mapping WorkingMemoryItem to a generic StorageProvider."""
    def __init__(self, provider: StorageProvider):
        self._provider = provider
        self._collection = "working_memory"
        
    def save(self, item: WorkingMemoryItem) -> None:
        self._provider.insert(self._collection, item.to_dict())
        
    def get(self, item_id: str) -> Optional[WorkingMemoryItem]:
        results = self._provider.query(self._collection, {"id": {"value": item_id}}, limit=1)
        if results:
            return WorkingMemoryItem.from_dict(results[0])
        return None
        
    def find(self, filters: Dict[str, Any], limit: int = 100) -> List[WorkingMemoryItem]:
        results = self._provider.query(self._collection, filters, limit=limit)
        return [WorkingMemoryItem.from_dict(r) for r in results]
        
    def remove(self, item_id: str) -> bool:
        return self._provider.delete(self._collection, item_id)
        
    def clear(self) -> None:
        self._provider.clear(self._collection)

class WorkingMemoryManager:
    """Manages short-term scratchpad memory with TTL expiration."""
    def __init__(self, provider: StorageProvider, event_bus: EventBus):
        self._repo = WorkingMemoryRepository(provider)
        self._event_bus = event_bus
        self._lock = threading.Lock()
        
    def store_context(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> WorkingMemoryItem:
        """Stores a value in working memory, replacing existing if present by key."""
        with self._lock:
            # We'll use the key as the identifier for O(1) lookups in this manager
            expires_at = time.time() + ttl_seconds if ttl_seconds else None
            
            item = WorkingMemoryItem(
                id=Identifier(value=key), # Reuse key as ID
                memory_type=MemoryType.WORKING,
                created_at=Timestamp(),
                key=key,
                value=value,
                ttl_seconds=ttl_seconds,
                expires_at=expires_at
            )
            self._repo.save(item)
            return item
            
    def get_context(self, key: str) -> Optional[Any]:
        """Retrieves a value. Automatically evicts if TTL has expired."""
        with self._lock:
            item = self._repo.get(key)
            if not item:
                return None
                
            if item.expires_at and time.time() > item.expires_at:
                # Lazy eviction
                self._repo.remove(key)
                self._event_bus.publish(Event(
                    topic="memory.working.evicted",
                    payload={"key": key},
                    source="memory.working"
                ))
                return None
                
            return item.value
            
    def delete_context(self, key: str) -> bool:
        with self._lock:
            return self._repo.remove(key)
            
    def clear_context(self) -> None:
        with self._lock:
            self._repo.clear()
