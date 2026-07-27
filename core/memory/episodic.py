import threading
from typing import Optional, Dict, Any, List

from core.models import Identifier, Timestamp, Event
from core.events import EventBus
from .enums import MemoryType
from .models import EpisodicEvent
from .interfaces import StorageProvider, MemoryRepository

class EpisodicMemoryRepository(MemoryRepository):
    def __init__(self, provider: StorageProvider):
        self._provider = provider
        self._collection = "episodic_memory"
        
    def save(self, item: EpisodicEvent) -> None:
        self._provider.insert(self._collection, item.to_dict())
        
    def get(self, item_id: str) -> Optional[EpisodicEvent]:
        results = self._provider.query(self._collection, {"id": {"value": item_id}}, limit=1)
        if results:
            return EpisodicEvent.from_dict(results[0])
        return None
        
    def find(self, filters: Dict[str, Any], limit: int = 100) -> List[EpisodicEvent]:
        results = self._provider.query(self._collection, filters, limit=limit)
        return [EpisodicEvent.from_dict(r) for r in results]
        
    def remove(self, item_id: str) -> bool:
        # Episodic memory is generally append-only, but expose for testing/cleanup
        return self._provider.delete(self._collection, item_id)

class EpisodicMemoryManager:
    """Manages chronological event logging. Append-only."""
    def __init__(self, provider: StorageProvider, event_bus: EventBus):
        self._repo = EpisodicMemoryRepository(provider)
        self._event_bus = event_bus
        self._lock = threading.Lock()
        
    def record_episode(self, event_type: str, payload: Dict[str, Any], source: str = "system") -> EpisodicEvent:
        with self._lock:
            event = EpisodicEvent(
                id=Identifier(),
                memory_type=MemoryType.EPISODIC,
                created_at=Timestamp(),
                event_type=event_type,
                payload=payload,
                source=source
            )
            self._repo.save(event)
            self._event_bus.publish(Event(
                topic="memory.episodic.recorded",
                payload=event.to_dict(),
                source="memory.episodic"
            ))
            return event
            
    def retrieve_episodes(self, filters: Optional[Dict[str, Any]] = None, limit: int = 100) -> List[EpisodicEvent]:
        with self._lock:
            f = filters or {}
            # The StorageProvider returns dicts, repo returns objects
            return self._repo.find(f, limit=limit)
            
    def search_episodes(self, event_type: str, limit: int = 100) -> List[EpisodicEvent]:
        with self._lock:
            return self._repo.find({"event_type": event_type}, limit=limit)
