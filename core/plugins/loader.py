import importlib.util
import os
import sys

from .enums import PluginState
from .exceptions import PluginLoadError
from .interfaces import PluginLoader
from .models import PluginDescriptor


class DynamicPluginLoader(PluginLoader):
    """Dynamically loads Python modules from plugin paths."""

    def load(self, descriptor: PluginDescriptor) -> PluginDescriptor:
        if descriptor.state != PluginState.DISCOVERED:
            raise PluginLoadError(f"Plugin {descriptor.manifest.id.value} is not in DISCOVERED state.")

        entrypoint_file = descriptor.manifest.entrypoint
        module_path = os.path.join(descriptor.path, entrypoint_file)

        if not os.path.isfile(module_path):
            raise PluginLoadError(f"Entrypoint file {entrypoint_file} not found in {descriptor.path}.")

        module_name = f"jarvis.plugins.{descriptor.manifest.id.value}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise PluginLoadError(f"Could not create module spec for {module_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            return PluginDescriptor(
                manifest=descriptor.manifest,
                metadata=descriptor.metadata,
                state=PluginState.LOADED,
                path=descriptor.path,
                health=descriptor.health,
                module_ref=module
            )
        except Exception as e:  # noqa: BLE001
            raise PluginLoadError(f"Failed to load plugin {descriptor.manifest.id.value}: {e}")

    def unload(self, descriptor: PluginDescriptor) -> PluginDescriptor:
        module_name = f"jarvis.plugins.{descriptor.manifest.id.value}"
        if module_name in sys.modules:
            del sys.modules[module_name]

        return PluginDescriptor(
            manifest=descriptor.manifest,
            metadata=descriptor.metadata,
            state=PluginState.DISCOVERED,  # Revert state
            path=descriptor.path,
            health=descriptor.health,
            module_ref=None
        )
