import builtins

from .exceptions import DependencyError
from .interfaces import DependencyResolver
from .models import PackageMetadata


class DefaultDependencyResolver(DependencyResolver):
    """Resolves dependency graphs using topological sorting."""

    def resolve(self, packages: builtins.list[PackageMetadata]) -> builtins.list[PackageMetadata]:
        # Mapping from package id to its metadata
        pkg_map = {p.id.value: p for p in packages}
        
        # Graph represents edges from a package to its dependencies
        graph: dict[str, builtins.list[str]] = {p.id.value: [dep.id.value for dep in p.dependencies] for p in packages}

        # Check for missing dependencies
        for pid, deps in graph.items():
            for dep in deps:
                if dep not in pkg_map:
                    raise DependencyError(f"Package {pid} depends on missing package {dep}")

        # Topological sort using DFS
        visited: set[str] = set()
        path: set[str] = set()
        ordered_ids: builtins.list[str] = []

        def dfs(node: str) -> None:
            if node in path:
                raise DependencyError(f"Circular dependency detected involving package {node}")
            if node in visited:
                return

            path.add(node)
            for neighbor in graph.get(node, []):
                dfs(neighbor)
            
            path.remove(node)
            visited.add(node)
            ordered_ids.append(node)

        for node in graph:
            if node not in visited:
                dfs(node)

        return [pkg_map[pid] for pid in ordered_ids]
