"""
Public facade for the Personal Knowledge Index subsystem.
"""

import logging
import time
from pathlib import Path

from config.config import JarvisConfig
from core.events.bus import EventBus
from core.llm import LLMClient

from .embeddings import EmbeddingsEngine
from .registry import KnowledgeSearchResult, SQLiteKnowledgeRegistry
from .scheduler import KnowledgeScheduler
from .telemetry import KnowledgeTelemetry

logger = logging.getLogger(__name__)

class KnowledgeManager:
    """Facade for the PKI subsystem, managing indexing and semantic search."""

    def __init__(self, config: JarvisConfig, llm_client: LLMClient, event_bus: EventBus) -> None:
        self._config = config
        
        # Determine default roots (user home directories)
        home = Path.home()
        self._root_dirs = [
            str(home / "Documents"),
            str(home / "Desktop"),
            str(home / "Downloads"),
            str(home / "Projects")
        ]
        
        # Ensure parent dir for DB exists
        Path(self._config.knowledge_db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self._registry = SQLiteKnowledgeRegistry(self._config.knowledge_db_path)
        self._engine = EmbeddingsEngine(llm_client)
        self._telemetry = KnowledgeTelemetry(event_bus)
        
        self._scheduler = KnowledgeScheduler(
            registry=self._registry,
            engine=self._engine,
            telemetry=self._telemetry,
            root_dirs=self._root_dirs,
            interval_seconds=self._config.knowledge_scan_interval_seconds
        )
        
        # Preload corpus into memory for search queries (lazy load later for scale)
        self._corpus_cache = None
        
    def start_background_indexing(self) -> None:
        """Starts the background incremental indexing process."""
        self._scheduler.start()
        
    def stop(self) -> None:
        """Stops background processes."""
        self._scheduler.stop()
        
    def force_index_sync(self) -> None:
        """Forces an immediate synchronous indexing pass."""
        self._scheduler.run_once()
        self._corpus_cache = None  # invalidate cache
        
    def search(self, query: str, limit: int = 5) -> list[KnowledgeSearchResult]:
        """Perform a semantic search against the user's personal files."""
        start_time = time.time()
        
        if self._corpus_cache is None:
            self._corpus_cache = self._registry.get_all_chunks_with_embeddings()
            
        results = self._engine.search(query, self._corpus_cache, limit=limit)
        
        duration = time.time() - start_time
        self._telemetry.emit_search_performed(query, len(results), duration)
        
        return results
