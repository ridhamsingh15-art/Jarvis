import threading
from typing import Any, Protocol, runtime_checkable

from .models import MemoryItem


@runtime_checkable
class StorageProvider(Protocol):
    """
    Abstracts physical persistence mechanisms (SQLite, Redis, VectorDB).
    """
    def insert(self, collection: str, data: dict[str, Any]) -> None:
        ...
        
    def query(self, collection: str, filters: dict[str, Any], limit: int = 100) -> list[dict[str, Any]]:
        ...
        
    def delete(self, collection: str, item_id: str) -> bool:
        ...
        
    def clear(self, collection: str) -> None:
        ...

class InMemoryStorageProvider(StorageProvider):
    """
    Default thread-safe, persistence-agnostic memory storage provider.
    Provides immediate out-of-the-box compatibility without external databases.
    """
    def __init__(self):
        self._collections: dict[str, dict[str, dict[str, Any]]] = {}
        self._lock = threading.RLock()
        
    def _get_collection(self, name: str) -> dict[str, dict[str, Any]]:
        if name not in self._collections:
            self._collections[name] = {}
        return self._collections[name]

    def insert(self, collection: str, data: dict[str, Any]) -> None:
        with self._lock:
            col = self._get_collection(collection)
            item_id = data.get("id")
            if item_id:
                # Store the ID value safely
                if isinstance(item_id, dict):
                    item_id_val = str(item_id.get("value", ""))
                else:
                    item_id_val = str(item_id)
                col[item_id_val] = data

    def query(self, collection: str, filters: dict[str, Any], limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            col = self._get_collection(collection)
            results = []
            for item in col.values():
                match = True
                for k, v in filters.items():
                    if item.get(k) != v:
                        match = False
                        break
                if match:
                    results.append(item)
                    if len(results) >= limit:
                        break
            return results

    def delete(self, collection: str, item_id: str) -> bool:
        with self._lock:
            col = self._get_collection(collection)
            if item_id in col:
                del col[item_id]
                return True
            return False
            
    def clear(self, collection: str) -> None:
        with self._lock:
            if collection in self._collections:
                self._collections[collection].clear()

@runtime_checkable
class MemoryRepository(Protocol):
    """
    Domain-specific memory repository abstracting storage formats.
    """
    def save(self, item: MemoryItem) -> None:
        ...
    def get(self, item_id: str) -> MemoryItem | None:
        ...
    def find(self, filters: dict[str, Any], limit: int = 100) -> list[MemoryItem]:
        ...
    def remove(self, item_id: str) -> bool:
        ...
