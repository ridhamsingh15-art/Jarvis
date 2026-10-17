import threading

from .models import Entity, Relation


class KnowledgeGraph:
    def __init__(self) -> None:
        self.entities: dict[str, Entity] = {}
        self.relations: list[Relation] = []
        self._lock = threading.RLock()

    def add_entity(self, entity: Entity) -> None:
        with self._lock:
            self.entities[entity.id] = entity

    def add_relation(self, relation: Relation) -> None:
        with self._lock:
            self.relations.append(relation)

    def get_relations(self, source_id: str) -> list[Relation]:
        with self._lock:
            return [r for r in self.relations if r.source_id == source_id]
