from typing import Any

from core.events import EventBus
from core.runtime import BaseComponent, ComponentMetadata, HealthReport, RuntimeState

from .episodic import EpisodicMemoryManager
from .interfaces import StorageProvider
from .models import EpisodicEvent, SemanticFact
from .semantic import SemanticMemoryManager
from .working import WorkingMemoryManager


class MemoryManager(BaseComponent):
    """
    Unified Facade orchestrating Working, Episodic, and Semantic memory operations.
    Acts as a RuntimeComponent within JARVIS AIOS.
    """
    def __init__(self, provider: StorageProvider, event_bus: EventBus):
        super().__init__(ComponentMetadata(id="MemoryEngine", name="Memory", version="1.0.0"))
        self._provider = provider
        self._event_bus = event_bus
        
        self.working = WorkingMemoryManager(provider, event_bus)
        self.episodic = EpisodicMemoryManager(provider, event_bus)
        self.semantic = SemanticMemoryManager(provider, event_bus)
        
        # Subscribe to automated lifecycle events for Episodic logging
        self._event_bus.subscribe("task.completed", self._on_task_event)
        self._event_bus.subscribe("task.failed", self._on_task_event)
        self._event_bus.subscribe("workflow.completed", self._on_workflow_event)
        self._event_bus.subscribe("workflow.failed", self._on_workflow_event)

    def _on_task_event(self, event):
        """Automatically log task completion/failure to episodic memory."""
        self.episodic.record_episode(
            event_type=event.topic,
            payload=event.payload,
            source="system.task"
        )
        
    def _on_workflow_event(self, event):
        """Automatically log workflow completion/failure to episodic memory."""
        self.episodic.record_episode(
            event_type=event.topic,
            payload=event.payload,
            source="system.workflow"
        )

    # --- Working Facade ---
    def store_context(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        self.working.store_context(key, value, ttl_seconds)
        
    def get_context(self, key: str) -> Any | None:
        return self.working.get_context(key)
        
    def delete_context(self, key: str) -> bool:
        return self.working.delete_context(key)
        
    def clear_context(self) -> None:
        self.working.clear_context()

    # --- Episodic Facade ---
    def record_episode(self, event_type: str, payload: dict[str, Any], source: str = "system") -> EpisodicEvent:
        return self.episodic.record_episode(event_type, payload, source)
        
    def retrieve_episodes(self, filters: dict[str, Any] | None = None, limit: int = 100) -> list[EpisodicEvent]:
        return self.episodic.retrieve_episodes(filters, limit)
        
    def search_episodes(self, event_type: str, limit: int = 100) -> list[EpisodicEvent]:
        return self.episodic.search_episodes(event_type, limit)

    # --- Semantic Facade ---
    def store_fact(self, entity: str, relationship: str, target: str, metadata: dict[str, Any] | None = None) -> SemanticFact:
        return self.semantic.store_fact(entity, relationship, target, metadata)
        
    def query_facts(self, entity: str, limit: int = 100) -> list[SemanticFact]:
        return self.semantic.query_facts(entity, limit)
        
    def update_fact(self, fact_id: str, relationship: str | None = None, target: str | None = None) -> SemanticFact:
        return self.semantic.update_fact(fact_id, relationship, target)
        
    def remove_fact(self, fact_id: str) -> bool:
        return self.semantic.remove_fact(fact_id)

    # --- RuntimeComponent Overrides ---
    async def _do_start(self) -> None:
        pass
        
    async def _do_stop(self) -> None:
        pass
        
    async def health(self) -> HealthReport:
        is_healthy = self.state == RuntimeState.RUNNING
        from core.runtime.enums import HealthState
        return HealthReport(
            component_id=self.metadata.id,
            state=HealthState.HEALTHY if is_healthy else HealthState.DEGRADED,
            details={"provider": self._provider.__class__.__name__}
        )
