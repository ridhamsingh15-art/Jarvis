import threading
from typing import Any

from core.events import EventBus
from core.models import Event, Identifier, Timestamp

from .enums import MemoryType
from .exceptions import MemoryNotFoundError
from .interfaces import MemoryItem, MemoryRepository, StorageProvider
from .models import SemanticFact


class SemanticMemoryRepository(MemoryRepository):
    def __init__(self, provider: StorageProvider):
        self._provider = provider
        self._collection = "semantic_memory"
        
    def save(self, item: Any) -> None:
        if not isinstance(item, SemanticFact):
            raise TypeError("Expected SemanticFact")
        self._provider.insert(self._collection, item.to_dict())
        
    def get(self, item_id: str) -> SemanticFact | None:
        results = self._provider.query(self._collection, {"id": {"value": item_id}}, limit=1)
        if results:
            return SemanticFact.from_dict(results[0])
        return None
        
    def find(self, filters: dict[str, Any], limit: int = 100) -> list[MemoryItem]:
        results = self._provider.query(self._collection, filters, limit=limit)
        return [SemanticFact.from_dict(r) for r in results]
        
    def remove(self, item_id: str) -> bool:
        return self._provider.delete(self._collection, item_id)

class SemanticMemoryManager:
    """Manages knowledge facts and entity relationships."""
    def __init__(self, provider: StorageProvider, event_bus: EventBus):
        self._repo = SemanticMemoryRepository(provider)
        self._event_bus = event_bus
        self._lock = threading.Lock()
        
    def store_fact(self, entity: str, relationship: str, target: str, metadata: dict[str, Any] | None = None) -> SemanticFact:
        with self._lock:
            fact = SemanticFact(
                id=Identifier(),
                memory_type=MemoryType.SEMANTIC,
                created_at=Timestamp(),
                entity=entity,
                relationship=relationship,
                target=target,
                metadata=metadata or {}
            )
            self._repo.save(fact)
            self._event_bus.publish(Event(
                topic="memory.semantic.updated",
                payload={"action": "stored", "fact_id": fact.id.value},
                source="memory.semantic"
            ))
            return fact
            
    def query_facts(self, entity: str, limit: int = 100) -> list[SemanticFact]:
        from typing import cast
        return cast(list[SemanticFact], self._repo.find({"entity": entity}, limit=limit))
            
    def update_fact(self, fact_id: str, relationship: str | None = None, target: str | None = None) -> SemanticFact:
        with self._lock:
            existing = self._repo.get(fact_id)
            if not existing:
                raise MemoryNotFoundError(f"Fact {fact_id} not found.")
                
            # Treat semantic facts as immutable replacements
            import dataclasses
            kwargs: dict[str, Any] = {}
            if relationship: kwargs["relationship"] = relationship
            if target: kwargs["target"] = target
            
            updated = dataclasses.replace(existing, **kwargs)
            self._repo.save(updated)
            
            self._event_bus.publish(Event(
                topic="memory.semantic.updated",
                payload={"action": "updated", "fact_id": fact_id},
                source="memory.semantic"
            ))
            return updated
            
    def remove_fact(self, fact_id: str) -> bool:
        with self._lock:
            success = self._repo.remove(fact_id)
            if success:
                self._event_bus.publish(Event(
                    topic="memory.semantic.updated",
                    payload={"action": "removed", "fact_id": fact_id},
                    source="memory.semantic"
                ))
            return success
