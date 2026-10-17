import builtins
import re

from .exceptions import PluginDependencyError, PluginValidationError
from .interfaces import PluginValidator
from .models import PluginDescriptor, PluginManifest


class DefaultPluginValidator(PluginValidator):
    """Validates plugin manifests and dependency graphs."""

    def __init__(self, current_sdk_version: str, current_runtime: str) -> None:
        self._sdk_version = current_sdk_version
        self._runtime = current_runtime

    def validate_manifest(self, manifest: PluginManifest) -> bool:
        if not manifest.id or not manifest.id.value:
            raise PluginValidationError("Plugin ID is required.")
        if not manifest.name:
            raise PluginValidationError("Plugin name is required.")
        if not manifest.entrypoint:
            raise PluginValidationError("Plugin entrypoint is required.")

        # Simple regex for semver-like format X.Y.Z
        if not re.match(r'^\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.-]+)?$', manifest.sdk_version):
            raise PluginValidationError(f"Invalid SDK version format: {manifest.sdk_version}")
            
        if manifest.compatible_runtime != self._runtime:
            raise PluginValidationError(f"Incompatible runtime: {manifest.compatible_runtime} != {self._runtime}")

        return True

    def validate_graph(self, descriptors: builtins.list[PluginDescriptor]) -> bool:
        # Check for duplicate IDs
        ids = set()
        for d in descriptors:
            pid = d.manifest.id.value
            if pid in ids:
                raise PluginValidationError(f"Duplicate plugin ID found: {pid}")
            ids.add(pid)

        # Check for missing dependencies and cycles
        graph: dict[str, builtins.list[str]] = {}
        for d in descriptors:
            graph[d.manifest.id.value] = [dep.id.value for dep in d.manifest.dependencies]

        for pid, deps in graph.items():
            for dep in deps:
                if dep not in ids:
                    raise PluginDependencyError(f"Plugin {pid} depends on missing plugin {dep}")

        # Cycle detection using DFS
        visited: set[str] = set()
        path: set[str] = set()

        def dfs(node: str) -> bool:
            if node in path:
                return True # Cycle detected
            if node in visited:
                return False
                
            visited.add(node)
            path.add(node)
            
            for neighbor in graph.get(node, []):
                if dfs(neighbor):
                    return True
                    
            path.remove(node)
            return False

        for node in graph:
            if dfs(node):
                raise PluginDependencyError(f"Dependency cycle detected involving plugin {node}")

        return True
