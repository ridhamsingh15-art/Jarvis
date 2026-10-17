import builtins
import json
import os

from core.models.primitives import Identifier

from .enums import PluginCapability, PluginState, PluginType
from .interfaces import PluginDiscoverer
from .models import PluginDependency, PluginDescriptor, PluginManifest, PluginMetadata


class FileSystemPluginDiscoverer(PluginDiscoverer):
    """Discovers plugins by scanning directories for manifest.json files."""

    def discover(self, plugins_dir: str) -> builtins.list[PluginDescriptor]:
        descriptors: builtins.list[PluginDescriptor] = []
        if not os.path.isdir(plugins_dir):
            return descriptors

        for entry in os.scandir(plugins_dir):
            if entry.is_dir():
                manifest_path = os.path.join(entry.path, "manifest.json")
                if os.path.isfile(manifest_path):
                    try:
                        manifest = self._parse_manifest(manifest_path)
                        descriptor = PluginDescriptor(
                            manifest=manifest,
                            metadata=PluginMetadata(),
                            state=PluginState.DISCOVERED,
                            path=entry.path
                        )
                        descriptors.append(descriptor)
                    except Exception:  # noqa: BLE001, S110
                        # Ignore invalid folders
                        pass

        return descriptors

    def _parse_manifest(self, path: str) -> PluginManifest:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        dependencies = [
            PluginDependency(id=Identifier(dep["id"]), version_spec=dep["version_spec"])
            for dep in data.get("dependencies", [])
        ]
        capabilities = [PluginCapability(c) for c in data.get("capabilities", [])]
        
        return PluginManifest(
            id=Identifier(data["id"]),
            name=data["name"],
            author=data["author"],
            version=data["version"],
            sdk_version=data["sdk_version"],
            compatible_runtime=data["compatible_runtime"],
            entrypoint=data["entrypoint"],
            plugin_type=PluginType(data.get("plugin_type", PluginType.THIRD_PARTY.value)),
            dependencies=dependencies,
            capabilities=capabilities,
            permissions=data.get("permissions", [])
        )
