from .enums import PluginState
from .exceptions import PluginLifecycleError
from .interfaces import PluginLifecycle
from .models import PluginDescriptor


class DefaultPluginLifecycle(PluginLifecycle):
    """Orchestrates state machine transitions for plugins."""

    def initialize(self, descriptor: PluginDescriptor) -> PluginDescriptor:
        if descriptor.state != PluginState.LOADED:
            raise PluginLifecycleError(f"Cannot initialize plugin {descriptor.manifest.id.value} from state {descriptor.state}.")
            
        try:
            module = descriptor.module_ref
            if module and hasattr(module, "plugin_initialize"):
                module.plugin_initialize()
                
            return PluginDescriptor(
                manifest=descriptor.manifest,
                metadata=descriptor.metadata,
                state=PluginState.INITIALIZED,
                path=descriptor.path,
                health=descriptor.health,
                module_ref=descriptor.module_ref
            )
        except Exception as e:  # noqa: BLE001
            raise PluginLifecycleError(f"Failed to initialize plugin {descriptor.manifest.id.value}: {e}")

    def start(self, descriptor: PluginDescriptor) -> PluginDescriptor:
        if descriptor.state not in (PluginState.INITIALIZED, PluginState.STOPPED):
            raise PluginLifecycleError(f"Cannot start plugin {descriptor.manifest.id.value} from state {descriptor.state}.")

        try:
            module = descriptor.module_ref
            if module and hasattr(module, "plugin_start"):
                module.plugin_start()
                
            return PluginDescriptor(
                manifest=descriptor.manifest,
                metadata=descriptor.metadata,
                state=PluginState.RUNNING,
                path=descriptor.path,
                health=descriptor.health,
                module_ref=descriptor.module_ref
            )
        except Exception as e:  # noqa: BLE001
            raise PluginLifecycleError(f"Failed to start plugin {descriptor.manifest.id.value}: {e}")

    def stop(self, descriptor: PluginDescriptor) -> PluginDescriptor:
        if descriptor.state != PluginState.RUNNING:
            raise PluginLifecycleError(f"Cannot stop plugin {descriptor.manifest.id.value} from state {descriptor.state}.")

        try:
            module = descriptor.module_ref
            if module and hasattr(module, "plugin_stop"):
                module.plugin_stop()
                
            return PluginDescriptor(
                manifest=descriptor.manifest,
                metadata=descriptor.metadata,
                state=PluginState.STOPPED,
                path=descriptor.path,
                health=descriptor.health,
                module_ref=descriptor.module_ref
            )
        except Exception as e:  # noqa: BLE001
            raise PluginLifecycleError(f"Failed to stop plugin {descriptor.manifest.id.value}: {e}")
