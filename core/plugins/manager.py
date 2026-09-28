import builtins

from core.events.bus import EventBus
from core.models.domain import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport
from core.telemetry import AsyncLogger

from .enums import PluginState
from .interfaces import (
    PluginDiscoverer,
    PluginLifecycle,
    PluginLoader,
    PluginRegistry,
    PluginSandbox,
    PluginValidator,
)
from .models import PluginDescriptor


class PluginManager(RuntimeComponent):
    """Orchestrates the plugin runtime subsystem."""

    def __init__(
        self,
        discoverer: PluginDiscoverer,
        validator: PluginValidator,
        loader: PluginLoader,
        sandbox: PluginSandbox,
        lifecycle: PluginLifecycle,
        registry: PluginRegistry,
        event_bus: EventBus,
        logger: AsyncLogger,
        plugins_dir: str
    ) -> None:
        self._discoverer = discoverer
        self._validator = validator
        self._loader = loader
        self._sandbox = sandbox
        self._lifecycle = lifecycle
        self._registry = registry
        self._event_bus = event_bus
        self._logger = logger
        self._plugins_dir = plugins_dir

        self._state = ComponentState.INITIALIZED
        self._metadata = ComponentMetadata(
            id="core.plugins",
            name="Plugin Runtime Subsystem",
            version="1.0.0",
            dependencies=["core.events", "core.telemetry"]
        )

    @property
    def metadata(self) -> ComponentMetadata:
        return self._metadata

    @property
    def state(self) -> ComponentState:
        return self._state

    async def start(self) -> None:
        if self._state in (ComponentState.STARTING, ComponentState.RUNNING):
            return

        self._state = ComponentState.STARTING
        self._logger.info("Starting Plugin Runtime Subsystem...")

        # Discover, validate, load, initialize, and start plugins
        self.discover()
        self.load()
        
        # Start all loaded plugins
        for descriptor in self.list_plugins():
            if descriptor.state == PluginState.INITIALIZED:
                try:
                    updated = self._lifecycle.start(descriptor)
                    self._registry.register(updated)
                    self._publish_event("plugin.started", updated)
                except Exception as e:  # noqa: BLE001
                    self._logger.error(f"Failed to start plugin {descriptor.manifest.id.value}: {e}")

        self._state = ComponentState.RUNNING
        self._logger.info("Plugin Runtime Subsystem started successfully.")

    async def stop(self) -> None:
        if self._state != ComponentState.RUNNING:
            return

        self._state = ComponentState.STOPPING
        self._logger.info("Stopping Plugin Runtime Subsystem...")

        # Stop all running plugins
        for descriptor in self.list_plugins():
            if descriptor.state == PluginState.RUNNING:
                try:
                    updated = self._lifecycle.stop(descriptor)
                    self._registry.register(updated)
                    self._publish_event("plugin.stopped", updated)
                except Exception as e:  # noqa: BLE001
                    self._logger.error(f"Failed to stop plugin {descriptor.manifest.id.value}: {e}")
                    
        self.unload()

        self._state = ComponentState.STOPPED
        self._logger.info("Plugin Runtime Subsystem stopped.")

    async def health(self) -> HealthReport:
        try:
            total = len(self._registry.list())
            running = len([p for p in self._registry.list() if p.state == PluginState.RUNNING])
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.HEALTHY,
                details={"total_plugins": total, "running_plugins": running}
            )
        except Exception as e:  # noqa: BLE001
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.UNHEALTHY,
                error=str(e)
            )

    def discover(self) -> None:
        descriptors = self._discoverer.discover(self._plugins_dir)
        for d in descriptors:
            try:
                if self._validator.validate_manifest(d.manifest):
                    self._registry.register(d)
                    self._publish_event("plugin.discovered", d)
            except Exception as e:  # noqa: BLE001
                self._logger.error(f"Plugin {d.manifest.id.value} failed validation: {e}")

    def load(self) -> None:
        descriptors = self._registry.list()
        # Verify graph before loading
        try:
            self._validator.validate_graph(descriptors)
        except Exception as e:  # noqa: BLE001
            self._logger.error(f"Plugin dependency graph validation failed: {e}")
            return

        for descriptor in descriptors:
            if descriptor.state == PluginState.DISCOVERED:
                try:
                    loaded = self._loader.load(descriptor)
                    self._registry.register(loaded)
                    self._sandbox.track(loaded)
                    self._publish_event("plugin.loaded", loaded)
                    
                    initialized = self._lifecycle.initialize(loaded)
                    self._registry.register(initialized)
                except Exception as e:  # noqa: BLE001
                    self._logger.error(f"Failed to load plugin {descriptor.manifest.id.value}: {e}")

    def reload(self) -> None:
        self.unload()
        self.discover()
        self.load()

    def unload(self) -> None:
        for descriptor in self._registry.list():
            if descriptor.state in (PluginState.LOADED, PluginState.INITIALIZED, PluginState.STOPPED):
                try:
                    unloaded = self._loader.unload(descriptor)
                    self._registry.register(unloaded)
                    self._publish_event("plugin.unloaded", unloaded)
                except Exception as e:  # noqa: BLE001
                    self._logger.error(f"Failed to unload plugin {descriptor.manifest.id.value}: {e}")

    def enable(self, plugin_id: Identifier) -> None:
        descriptor = self._registry.get(plugin_id)
        if descriptor and descriptor.state == PluginState.DISABLED:
            # Revert to stopped, wait for start
            updated = PluginDescriptor(
                manifest=descriptor.manifest,
                metadata=descriptor.metadata,
                state=PluginState.STOPPED,
                path=descriptor.path,
                health=descriptor.health,
                module_ref=descriptor.module_ref
            )
            self._registry.register(updated)

    def disable(self, plugin_id: Identifier) -> None:
        descriptor = self._registry.get(plugin_id)
        if descriptor and descriptor.state != PluginState.DISABLED:
            # Stop if running
            if descriptor.state == PluginState.RUNNING:
                descriptor = self._lifecycle.stop(descriptor)
            
            updated = PluginDescriptor(
                manifest=descriptor.manifest,
                metadata=descriptor.metadata,
                state=PluginState.DISABLED,
                path=descriptor.path,
                health=descriptor.health,
                module_ref=descriptor.module_ref
            )
            self._registry.register(updated)

    def list_plugins(self) -> builtins.list[PluginDescriptor]:
        return self._registry.list()

    def _publish_event(self, topic: str, descriptor: PluginDescriptor) -> None:
        event = Event(
            topic=topic,
            payload={"plugin_id": descriptor.manifest.id.value, "state": descriptor.state.value},
            source=self.metadata.id
        )
        self._event_bus.publish(event)
