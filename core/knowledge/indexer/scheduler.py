"""
Background scheduler to incrementally run the PKI updates.
"""

import logging
import threading
import time

from .chunking import get_chunks
from .embeddings import EmbeddingsEngine
from .registry import SQLiteKnowledgeRegistry
from .telemetry import KnowledgeTelemetry
from .watcher import FileWatcher

logger = logging.getLogger(__name__)


class KnowledgeScheduler:
    """Runs periodic background scans without blocking the main event loop or interactive requests."""

    _interactive_active_event = threading.Event()
    _is_indexing = False
    _last_interactive_time: float = 0.0
    _cooldown_seconds: float = 2.5

    @classmethod
    def set_interactive_active(cls, active: bool) -> None:
        """Signal that a foreground interactive request is active or completed."""
        cls._last_interactive_time = time.time()
        if active:
            cls._interactive_active_event.set()
        else:
            cls._interactive_active_event.clear()

    @classmethod
    def is_interactive_active(cls) -> bool:
        if cls._interactive_active_event.is_set():
            return True
        # Keep yielding for cooldown period after interactive turn completes
        if time.time() - cls._last_interactive_time < cls._cooldown_seconds:
            return True
        return False

    @classmethod
    def is_indexing(cls) -> bool:
        return cls._is_indexing

    def __init__(
        self,
        registry: SQLiteKnowledgeRegistry,
        engine: EmbeddingsEngine,
        telemetry: KnowledgeTelemetry,
        root_dirs: list[str],
        interval_seconds: int = 300
    ) -> None:
        self._registry = registry
        self._engine = engine
        self._telemetry = telemetry
        self._watcher = FileWatcher(registry, root_dirs)
        self._interval = interval_seconds
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._root_dirs = root_dirs

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
            
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="KnowledgeScheduler")
        self._thread.start()
        logger.info("Knowledge Scheduler started with interval %ds", self._interval)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def pause(self) -> None:
        self._pause_event.set()

    def resume(self) -> None:
        self._pause_event.clear()
            
    def run_once(self) -> None:
        """Runs a single indexing pass synchronously."""
        self._index_pass()

    def _run_loop(self) -> None:
        # Initial wait so we don't block startup CPU
        if self._stop_event.wait(10.0):
            return
            
        while not self._stop_event.is_set():
            try:
                self._index_pass()
            except Exception as e:
                logger.error("Error in KnowledgeScheduler: %s", e)
                
            # Wait for next interval or stop signal
            if self._stop_event.wait(self._interval):
                break

    def _index_pass(self) -> None:
        KnowledgeScheduler._is_indexing = True
        start_time = time.time()
        self._telemetry.emit_scan_started(self._root_dirs)
        
        try:
            modified_docs = self._watcher.get_modified_files()
            
            for doc in modified_docs:
                if self._stop_event.is_set():
                    break
                    
                # Pause/yield if an interactive user request is running
                while (self.is_interactive_active() or self._pause_event.is_set()) and not self._stop_event.is_set():
                    time.sleep(0.1)

                try:
                    chunks = get_chunks(doc)
                    for i, chunk in enumerate(chunks):
                        if self._stop_event.is_set():
                            break
                            
                        # Yield if interactive request arrived
                        while (self.is_interactive_active() or self._pause_event.is_set()) and not self._stop_event.is_set():
                            time.sleep(0.1)

                        self._engine.embed_chunk(chunk)
                        
                        # Cooperative yield between chunks to leave Ollama responsive for interactive inference
                        time.sleep(0.15)
                        
                    doc.last_indexed = time.time()
                    self._registry.upsert_document(doc)
                    self._registry.save_chunks(chunks)
                    time.sleep(0.3)
                    
                    self._telemetry.emit_document_indexed(doc.id, doc.path, len(chunks))
                except Exception as e:
                    logger.debug("Failed to index %s: %s", doc.path, e)
                    
            duration = time.time() - start_time
            self._telemetry.emit_scan_completed(len(modified_docs), duration)
        finally:
            KnowledgeScheduler._is_indexing = False

