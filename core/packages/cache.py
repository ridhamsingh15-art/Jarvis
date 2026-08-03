import threading
import time
from collections import OrderedDict

from core.models.primitives import Identifier

from .enums import CacheState
from .interfaces import PackageCache
from .models import PackageCacheEntry


class ThreadSafeLRUCache(PackageCache):
    """Thread-safe LRU cache for package archives."""

    def __init__(self, max_size_bytes: int = 1024 * 1024 * 1024) -> None:
        self._lock = threading.RLock()
        self._max_size = max_size_bytes
        self._current_size = 0
        # key: f"{package_id}:{version}" -> value: PackageCacheEntry
        self._cache: OrderedDict[str, PackageCacheEntry] = OrderedDict()

    def get(self, package_id: Identifier, version: str) -> PackageCacheEntry | None:
        with self._lock:
            key = f"{package_id.value}:{version}"
            if key in self._cache:
                entry = self._cache.pop(key)
                # Update last accessed
                updated_entry = PackageCacheEntry(
                    package_id=entry.package_id,
                    version=entry.version,
                    path=entry.path,
                    state=entry.state,
                    size=entry.size,
                    last_accessed=time.time()
                )
                self._cache[key] = updated_entry
                return updated_entry
            return None

    def put(self, package_id: Identifier, version: str, file_path: str) -> PackageCacheEntry:
        with self._lock:
            key = f"{package_id.value}:{version}"
            
            # Simple mock size (0 for tests, real stat in prod)
            import os
            size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            if key in self._cache:
                old_entry = self._cache.pop(key)
                self._current_size -= old_entry.size
                
            entry = PackageCacheEntry(
                package_id=package_id,
                version=version,
                path=file_path,
                state=CacheState.VALID,
                size=size,
                last_accessed=time.time()
            )
            
            self._cache[key] = entry
            self._current_size += size
            
            self._evict_if_needed()
            
            return entry

    def remove(self, package_id: Identifier, version: str) -> bool:
        with self._lock:
            key = f"{package_id.value}:{version}"
            if key in self._cache:
                entry = self._cache.pop(key)
                self._current_size -= entry.size
                
                import os
                if os.path.exists(entry.path):
                    try:
                        os.remove(entry.path)
                    except OSError:
                        pass
                return True
            return False

    def _evict_if_needed(self) -> None:
        while self._current_size > self._max_size and self._cache:
            _key, entry = self._cache.popitem(last=False)  # pop oldest
            self._current_size -= entry.size
            import os
            if os.path.exists(entry.path):
                try:
                    os.remove(entry.path)
                except OSError:
                    pass
