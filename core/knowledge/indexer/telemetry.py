"""
Telemetry for the Knowledge Indexer subsystem.
"""

import logging
from typing import Any

from core.events.bus import EventBus
from core.models import Event

logger = logging.getLogger(__name__)


class KnowledgeTelemetry:
    """Emits events related to indexing progress and search."""
    
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        
    def emit_scan_started(self, roots: list[str]) -> None:
        self._publish("knowledge.scan.started", {"roots": roots})
        
    def emit_scan_completed(self, num_found: int, duration_sec: float) -> None:
        self._publish("knowledge.scan.completed", {
            "num_found": num_found, 
            "duration_sec": duration_sec
        })
        
    def emit_document_indexed(self, doc_id: str, path: str, num_chunks: int) -> None:
        self._publish("knowledge.document.indexed", {
            "doc_id": doc_id,
            "path": path,
            "num_chunks": num_chunks
        })
        
    def emit_search_performed(self, query: str, num_results: int, duration_sec: float) -> None:
        self._publish("knowledge.search.performed", {
            "query": query,
            "num_results": num_results,
            "duration_sec": duration_sec
        })
        
    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        try:
            event = Event(
                topic=topic,
                payload=payload,
                source="knowledge.indexer"
            )
            self._event_bus.publish(event)
        except Exception as e:
            logger.debug("Failed to emit telemetry %s: %s", topic, e)
