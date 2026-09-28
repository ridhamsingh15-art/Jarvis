"""
Plugin Manifest helpers.

Provides a fluent builder for constructing plugin manifests programmatically
(useful for tests and the SDK), and a typed parser for reading manifest.json
files from disk.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Optional

from core.models.primitives import Identifier

from .enums import PluginCapability, PluginType
from .exceptions import PluginValidationError
from .models import PluginDependency, PluginManifest


class ManifestBuilder:
    """Fluent builder for PluginManifest objects."""

    def __init__(self, plugin_id: str, name: str) -> None:
        self._id = plugin_id
        self._name = name
        self._author = "Unknown"
        self._version = "0.1.0"
        self._sdk_version = "1.0.0"
        self._compatible_runtime = ">=2.0.0"
        self._entrypoint = "plugin.py"
        self._plugin_type = PluginType.THIRD_PARTY
        self._capabilities: list[PluginCapability] = []
        self._permissions: list[str] = []
        self._dependencies: list[PluginDependency] = []

    def author(self, author: str) -> "ManifestBuilder":
        self._author = author
        return self

    def version(self, version: str) -> "ManifestBuilder":
        self._version = version
        return self

    def sdk_version(self, sdk_version: str) -> "ManifestBuilder":
        self._sdk_version = sdk_version
        return self

    def compatible_runtime(self, runtime: str) -> "ManifestBuilder":
        self._compatible_runtime = runtime
        return self

    def entrypoint(self, entrypoint: str) -> "ManifestBuilder":
        self._entrypoint = entrypoint
        return self

    def plugin_type(self, plugin_type: PluginType) -> "ManifestBuilder":
        self._plugin_type = plugin_type
        return self

    def with_capability(self, capability: PluginCapability) -> "ManifestBuilder":
        self._capabilities.append(capability)
        return self

    def with_permission(self, permission: str) -> "ManifestBuilder":
        self._permissions.append(permission)
        return self

    def depends_on(self, dep_id: str, version_spec: str = ">=1.0.0") -> "ManifestBuilder":
        self._dependencies.append(
            PluginDependency(id=Identifier(dep_id), version_spec=version_spec)
        )
        return self

    def build(self) -> PluginManifest:
        return PluginManifest(
            id=Identifier(self._id),
            name=self._name,
            author=self._author,
            version=self._version,
            sdk_version=self._sdk_version,
            compatible_runtime=self._compatible_runtime,
            entrypoint=self._entrypoint,
            plugin_type=self._plugin_type,
            capabilities=list(self._capabilities),
            permissions=list(self._permissions),
            dependencies=list(self._dependencies),
        )


class ManifestParser:
    """Reads and parses a plugin's manifest.json from disk."""

    def parse_file(self, manifest_path: str) -> PluginManifest:
        if not os.path.isfile(manifest_path):
            raise PluginValidationError(f"Manifest file not found: {manifest_path}")

        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)

        return self.parse_dict(data)

    def parse_dict(self, data: dict) -> PluginManifest:
        """Parse a manifest from an already-loaded dict (useful in tests)."""
        required = ("id", "name", "author", "version", "sdk_version", "compatible_runtime", "entrypoint")
        missing = [k for k in required if k not in data]
        if missing:
            raise PluginValidationError(f"Manifest is missing required keys: {missing}")

        dependencies = [
            PluginDependency(id=Identifier(dep["id"]), version_spec=dep.get("version_spec", ">=0.0.0"))
            for dep in data.get("dependencies", [])
        ]

        capabilities = []
        for cap in data.get("capabilities", []):
            try:
                capabilities.append(PluginCapability(cap))
            except ValueError as e:
                raise PluginValidationError(f"Unknown capability: {cap}") from e

        plugin_type_raw = data.get("plugin_type", PluginType.THIRD_PARTY.value)
        try:
            plugin_type = PluginType(plugin_type_raw)
        except ValueError as e:
            raise PluginValidationError(f"Unknown plugin_type: {plugin_type_raw}") from e

        return PluginManifest(
            id=Identifier(data["id"]),
            name=data["name"],
            author=data["author"],
            version=data["version"],
            sdk_version=data["sdk_version"],
            compatible_runtime=data["compatible_runtime"],
            entrypoint=data["entrypoint"],
            plugin_type=plugin_type,
            capabilities=capabilities,
            permissions=data.get("permissions", []),
            dependencies=dependencies,
        )
