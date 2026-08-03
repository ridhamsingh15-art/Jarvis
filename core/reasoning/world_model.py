from .knowledge_graph import KnowledgeGraph


class WorldModel:
    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph

    def get_state(self) -> dict[str, str]:
        # Return a flattened representation of the active world
        with self.graph._lock:
            return {e.name: e.type.value for e in self.graph.entities.values()}
