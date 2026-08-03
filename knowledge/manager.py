import builtins
import threading

from core.events.bus import EventBus
from core.models.domain import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport
from core.telemetry import AsyncLogger

from .indexer import IIndexer
from .ingestion import IngestionPipeline
from .interfaces import IHybridRetriever
from .models import KnowledgeQuery, SearchResult


class KnowledgeManager(RuntimeComponent):
    """Public API for the Enterprise Knowledge Engine."""

    def __init__(
        self,
        indexer: IIndexer,
        ingestion_pipeline: IngestionPipeline,
        retriever: IHybridRetriever,
        event_bus: EventBus,
        logger: AsyncLogger
    ) -> None:
        self._indexer = indexer
        self._ingestion = ingestion_pipeline
        self._retriever = retriever
        self._event_bus = event_bus
        self._logger = logger

        self._lock = threading.RLock()
        
        self._state = ComponentState.INITIALIZED
        self._metadata = ComponentMetadata(
            id="core.knowledge",
            name="Enterprise Knowledge Engine",
            version="1.0.0",
            dependencies=["core.events", "core.telemetry"]
        )

    @property
    def metadata(self) -> ComponentMetadata:
        return self._metadata

    @property
    def state(self) -> ComponentState:
        return self._state

    async def start(self) -> None:
        if self._state in (ComponentState.STARTING, ComponentState.RUNNING):
            return
        self._state = ComponentState.STARTING
        self._logger.info("Starting Knowledge Engine...")
        self._state = ComponentState.RUNNING
        self._logger.info("Knowledge Engine started.")

    async def stop(self) -> None:
        if self._state != ComponentState.RUNNING:
            return
        self._state = ComponentState.STOPPING
        self._logger.info("Stopping Knowledge Engine...")
        self._state = ComponentState.STOPPED
        self._logger.info("Knowledge Engine stopped.")

    async def health(self) -> HealthReport:
        try:
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.HEALTHY,
                details={}
            )
        except Exception as e:  # noqa: BLE001
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.UNHEALTHY,
                error=str(e)
            )

    def index_file(self, file_path: str) -> Identifier | None:
        with self._lock:
            self._publish_event("knowledge.index.started", {"target": file_path})
            doc_id = self._ingestion.ingest(file_path)
            if doc_id:
                self._publish_event("knowledge.index.completed", {"document_id": doc_id.value})
                self._publish_event("knowledge.updated", {"document_id": doc_id.value})
            return doc_id

    def index_folder(self, folder_path: str) -> builtins.list[Identifier]:
        with self._lock:
            self._publish_event("knowledge.index.started", {"target": folder_path})
            
            files = self._indexer.index_folder(folder_path)
            doc_ids = []
            
            for f in files:
                doc_id = self._ingestion.ingest(f.value)
                if doc_id:
                    doc_ids.append(doc_id)
                    
            self._publish_event("knowledge.index.completed", {"indexed_count": str(len(doc_ids))})
            return doc_ids

    def remove(self, document_id: Identifier) -> None:
        with self._lock:
            self._ingestion.remove(document_id)
            self._publish_event("knowledge.updated", {"action": "removed", "document_id": document_id.value})

    def update(self, file_path: str, document_id: Identifier) -> Identifier | None:
        with self._lock:
            self.remove(document_id)
            return self.index_file(file_path)

    def search(self, query: KnowledgeQuery) -> builtins.list[SearchResult]:
        results = self._retriever.retrieve(query)
        self._publish_event("knowledge.search.completed", {"query": query.query_text, "hits": str(len(results))})
        return results

    def ask(self, query: str) -> str:
        # Trivial naive implementation combining search results into a string response.
        # In a real system, this would pass context to a Cognitive LLM block.
        k_query = KnowledgeQuery(query_text=query)
        results = self.search(k_query)
        
        if not results:
            return "I could not find any relevant information."
            
        return "\n\n".join(r.chunk.content for r in results)

    def _publish_event(self, topic: str, payload: dict[str, str]) -> None:
        event = Event(
            topic=topic,
            payload=payload,
            source=self.metadata.id
        )
        self._event_bus.publish(event)
