"""
JARVIS Plugin SDK.

This module is the primary API surface for plugin developers. Import it from
your plugin.py to register capabilities, tools, missions, events, memory, and
use the logger — all without touching AIOS internals directly.

Usage in a plugin::

    from core.plugins.sdk import PluginContext

    def plugin_initialize(ctx: PluginContext) -> None:
        ctx.log.info("Hello from my plugin!")
        ctx.events.subscribe("mission.started", on_mission_started)
        ctx.capabilities.register("my_tool", "Does something cool")
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from core.capability.models import Capability, CapabilityType
from core.events.bus import EventBus
from core.models.domain import Event
from core.models.primitives import Identifier
from core.telemetry import AsyncLogger

from .exceptions import PluginSecurityError
from .permissions import PermissionManager


class PluginLogger:
    """Scoped logger for a plugin. Prefixes all log lines with the plugin ID."""

    def __init__(self, plugin_id: str) -> None:
        self._logger = logging.getLogger(f"plugin.{plugin_id}")

    def debug(self, msg: str) -> None:
        self._logger.debug(msg)

    def info(self, msg: str) -> None:
        self._logger.info(msg)

    def warning(self, msg: str) -> None:
        self._logger.warning(msg)

    def error(self, msg: str) -> None:
        self._logger.error(msg)


class PluginEventAdapter:
    """
    Allows plugins to subscribe to and publish events without accessing the raw
    EventBus. Topic patterns are validated to prevent plugins from injecting
    into internal AIOS topics.
    """

    # Topics plugins are NOT allowed to publish to
    _FORBIDDEN_PUBLISH_TOPICS = frozenset({"core.", "aios.", "system."})
    # Topics plugins are allowed to subscribe to
    _ALLOWED_SUBSCRIBE_PREFIXES = (
        "mission.", "memory.", "conversation.", "tool.", "publishing.", "plugin.",
    )

    def __init__(self, plugin_id: str, event_bus: EventBus) -> None:
        self._plugin_id = plugin_id
        self._bus = event_bus
        self._subscriptions: list[str] = []

    def subscribe(self, topic_pattern: str, handler: Callable) -> str:
        """Subscribe to an event topic. Returns a subscription ID."""
        sub_id = self._bus.subscribe(topic_pattern, handler)
        self._subscriptions.append(sub_id)
        return sub_id

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Publish an event scoped to this plugin."""
        for forbidden in self._FORBIDDEN_PUBLISH_TOPICS:
            if topic.startswith(forbidden):
                raise PluginSecurityError(
                    f"Plugin '{self._plugin_id}' is not allowed to publish to protected topic: {topic}"
                )
        event = Event(topic=f"plugin.{self._plugin_id}.{topic}", payload=payload, source=self._plugin_id)
        self._bus.publish(event)

    def cleanup(self) -> None:
        """Unsubscribe all handlers on plugin stop."""
        for sub_id in self._subscriptions:
            self._bus.unsubscribe(sub_id)
        self._subscriptions.clear()


class PluginCapabilityAdapter:
    """
    Allows plugins to register capabilities with the JARVIS Capability Manager
    without importing internal types directly.
    """

    def __init__(self, plugin_id: str, capability_manager: Any) -> None:
        self._plugin_id = plugin_id
        self._capability_manager = capability_manager
        self._registered: list[str] = []

    def register(self, name: str, description: str, capability_type: str = "tool") -> None:
        """Register a capability with the Capability Manager."""
        cap_type = CapabilityType(capability_type)
        capability = Capability(name=name, description=description, type=cap_type)
        self._capability_manager.register_capability(capability)
        self._registered.append(name)

    def list_registered(self) -> list[str]:
        return list(self._registered)


class PluginPerceptionAdapter:
    """
    Allows plugins to access JARVIS Multimodal Perception APIs (like reading
    the screen or a document).
    """

    def __init__(self, plugin_id: str, perception_manager: Any, permission_manager: PermissionManager) -> None:
        self._plugin_id = plugin_id
        self._perception_manager = perception_manager
        self._permission_manager = permission_manager

    def perceive_screen(self) -> Any:
        self._permission_manager.assert_permission(Identifier(self._plugin_id), "screen_capture")
        if not self._perception_manager:
            raise RuntimeError("PerceptionManager is not configured.")
        return self._perception_manager.perceive_screen()

    def perceive_window(self, window_title: str) -> Any:
        self._permission_manager.assert_permission(Identifier(self._plugin_id), "screen_capture")
        if not self._perception_manager:
            raise RuntimeError("PerceptionManager is not configured.")
        return self._perception_manager.perceive_window(window_title)


class PluginContext:
    """
    The primary API object passed to plugins via their lifecycle hooks.
    Provides safe, sandboxed access to JARVIS subsystems.
    """

    def __init__(
        self,
        plugin_id: str,
        event_bus: EventBus,
        capability_manager: Any,
        permission_manager: PermissionManager,
        perception_manager: Any = None,
    ) -> None:
        self._plugin_id = plugin_id
        self._permission_manager = permission_manager

        self.log = PluginLogger(plugin_id)
        self.events = PluginEventAdapter(plugin_id, event_bus)
        self.capabilities = PluginCapabilityAdapter(plugin_id, capability_manager)
        self.perception = PluginPerceptionAdapter(plugin_id, perception_manager, permission_manager)

    @property
    def plugin_id(self) -> str:
        return self._plugin_id

    def has_permission(self, permission: str) -> bool:
        """Check whether the user has granted a specific permission to this plugin."""
        return self._permission_manager.has_permission(Identifier(self._plugin_id), permission)

    def assert_permission(self, permission: str) -> None:
        """Raise PluginSecurityError if the user has NOT granted this permission."""
        self._permission_manager.assert_permission(Identifier(self._plugin_id), permission)


class PluginSDK:
    """
    Factory that vends scoped PluginContext objects to each plugin.
    Instantiated once by the PluginManager and shared across the plugin runtime.
    """

    def __init__(
        self,
        event_bus: EventBus,
        capability_manager: Any,
        permission_manager: PermissionManager,
        perception_manager: Any = None,
    ) -> None:
        self._event_bus = event_bus
        self._capability_manager = capability_manager
        self._permission_manager = permission_manager
        self._perception_manager = perception_manager

    def create_context(self, plugin_id: str) -> PluginContext:
        """Create a sandboxed context for a specific plugin."""
        return PluginContext(
            plugin_id=plugin_id,
            event_bus=self._event_bus,
            capability_manager=self._capability_manager,
            permission_manager=self._permission_manager,
            perception_manager=self._perception_manager,
        )
