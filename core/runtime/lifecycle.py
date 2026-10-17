"""
Lifecycle orchestration and dependency resolution.
"""
from collections import defaultdict, deque

from .exceptions import ComponentLifecycleError
from .interfaces import RuntimeComponent
from .registry import ComponentRegistry


class LifecycleManager:
    """Resolves component DAG and orchestrates boot/shutdown phases."""

    def __init__(self, registry: ComponentRegistry) -> None:
        self._registry = registry

    def resolve_startup_order(self) -> list[RuntimeComponent]:
        components = self._registry.get_all()
        id_map = {c.metadata.id: c for c in components}

        in_degree = {c.metadata.id: 0 for c in components}
        graph = defaultdict(list)

        for comp in components:
            for dep in comp.metadata.dependencies:
                if dep not in id_map:
                    raise ComponentLifecycleError(
                        f"Missing dependency: {dep} required by {comp.metadata.id}"
                    )
                graph[dep].append(comp.metadata.id)
                in_degree[comp.metadata.id] += 1

        queue = deque([cid for cid in in_degree if in_degree[cid] == 0])
        sorted_order = []

        while queue:
            cid = queue.popleft()
            sorted_order.append(id_map[cid])
            for neighbor in graph[cid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_order) != len(components):
            raise ComponentLifecycleError("Cycle detected in component dependencies.")

        return sorted_order

    async def start_all(self) -> None:
        ordered = self.resolve_startup_order()
        for comp in ordered:
            await comp.start()

    async def stop_all(self) -> None:
        ordered = self.resolve_startup_order()
        # Stop in reverse dependency order
        for comp in reversed(ordered):
            await comp.stop()
