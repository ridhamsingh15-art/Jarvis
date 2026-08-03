import builtins
from abc import ABC, abstractmethod

from core.models.primitives import Identifier

from .enums import PluginCapability
from .models import PluginDescriptor, PluginManifest


class PluginDiscoverer(ABC):
    """Abstract interface for discovering plugins."""

    @abstractmethod
    def discover(self, plugins_dir: str) -> builtins.list[PluginDescriptor]:
        pass


class PluginValidator(ABC):
    """Abstract interface for validating plugin manifests and graphs."""

    @abstractmethod
    def validate_manifest(self, manifest: PluginManifest) -> bool:
        pass

    @abstractmethod
    def validate_graph(self, descriptors: builtins.list[PluginDescriptor]) -> bool:
        pass


class PluginLoader(ABC):
    """Abstract interface for dynamically loading plugins."""

    @abstractmethod
    def load(self, descriptor: PluginDescriptor) -> PluginDescriptor:
        pass

    @abstractmethod
    def unload(self, descriptor: PluginDescriptor) -> PluginDescriptor:
        pass


class PluginSandbox(ABC):
    """Abstract interface for tracking sandbox metadata and boundaries."""

    @abstractmethod
    def track(self, descriptor: PluginDescriptor) -> None:
        pass

    @abstractmethod
    def verify_permission(self, plugin_id: Identifier, permission: str) -> bool:
        pass


class PluginLifecycle(ABC):
    """Abstract interface for orchestrating plugin state transitions."""

    @abstractmethod
    def initialize(self, descriptor: PluginDescriptor) -> PluginDescriptor:
        pass

    @abstractmethod
    def start(self, descriptor: PluginDescriptor) -> PluginDescriptor:
        pass

    @abstractmethod
    def stop(self, descriptor: PluginDescriptor) -> PluginDescriptor:
        pass


class PluginRegistry(ABC):
    """Abstract interface for managing plugin descriptors."""

    @abstractmethod
    def register(self, descriptor: PluginDescriptor) -> None:
        pass

    @abstractmethod
    def remove(self, plugin_id: Identifier) -> bool:
        pass

    @abstractmethod
    def get(self, plugin_id: Identifier) -> PluginDescriptor | None:
        pass

    @abstractmethod
    def exists(self, plugin_id: Identifier) -> bool:
        pass

    @abstractmethod
    def list(self) -> builtins.list[PluginDescriptor]:
        pass

    @abstractmethod
    def find_by_capability(self, capability: PluginCapability) -> builtins.list[PluginDescriptor]:
        pass
