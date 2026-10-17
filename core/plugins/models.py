from dataclasses import dataclass, field
from typing import Any

from core.models import JarvisModel
from core.models.primitives import Identifier, Metadata, Timestamp

from .enums import PluginCapability, PluginState, PluginType


@dataclass(frozen=True, slots=True)
class PluginDependency(JarvisModel):
    """Immutable representation of a plugin dependency."""
    id: Identifier
    version_spec: str


@dataclass(frozen=True, slots=True)
class PluginManifest(JarvisModel):
    """Immutable representation of a plugin's manifest.json."""
    id: Identifier
    name: str
    author: str
    version: str
    sdk_version: str
    compatible_runtime: str
    entrypoint: str
    plugin_type: PluginType = PluginType.THIRD_PARTY
    dependencies: list[PluginDependency] = field(default_factory=list)
    capabilities: list[PluginCapability] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PluginMetadata(JarvisModel):
    """Immutable representation of runtime metadata for a plugin."""
    checksum: str | None = None
    signature: str | None = None
    metadata: Metadata = field(default_factory=Metadata)


@dataclass(frozen=True, slots=True)
class PluginHealth(JarvisModel):
    """Immutable representation of a plugin's health status."""
    is_healthy: bool
    last_check: Timestamp = field(default_factory=Timestamp)
    message: str | None = None


@dataclass(frozen=True, slots=True)
class PluginDescriptor(JarvisModel):
    """Immutable representation of a tracked plugin."""
    manifest: PluginManifest
    metadata: PluginMetadata
    state: PluginState
    path: str
    health: PluginHealth | None = None
    module_ref: Any = None  # Reference to the loaded Python module if loaded


@dataclass(frozen=True, slots=True)
class LifecycleEvent(JarvisModel):
    """Data packet for lifecycle transitions."""
    plugin_id: Identifier
    previous_state: PluginState | None
    new_state: PluginState
    timestamp: Timestamp = field(default_factory=Timestamp)
    message: str | None = None
