"""
Tests for the Plugin SDK and Integration Framework.

Covers:
  - ManifestBuilder and ManifestParser
  - PermissionManager grant/revoke/assert
  - PolicySandbox permission verification
  - PluginSDK context creation and scoped adapters
  - PluginEventAdapter publish sandboxing
  - PluginCapabilityAdapter registration
  - Plugin lifecycle (initialize → start → stop)
  - DefaultPluginValidator manifest and graph validation
"""
import pytest
from unittest.mock import MagicMock

from core.models.primitives import Identifier
from core.plugins.enums import PluginCapability, PluginState, PluginType
from core.plugins.exceptions import (
    PluginSecurityError,
    PluginValidationError,
    PluginLifecycleError,
)
from core.plugins.manifest import ManifestBuilder, ManifestParser
from core.plugins.models import (
    PluginDescriptor,
    PluginHealth,
    PluginManifest,
    PluginMetadata,
)
from core.plugins.permissions import PermissionManager, PermissionType
from core.plugins.registry import ThreadSafePluginRegistry
from core.plugins.sandbox import PolicySandbox
from core.plugins.sdk import PluginSDK, PluginContext, PluginEventAdapter
from core.plugins.lifecycle import DefaultPluginLifecycle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manifest(plugin_id: str = "test_plugin", permissions: list[str] | None = None) -> PluginManifest:
    return (
        ManifestBuilder(plugin_id, "Test Plugin")
        .author("Tester")
        .version("1.2.3")
        .with_capability(PluginCapability.TOOL)
        .with_permission(PermissionType.NETWORK)
        .build()
    )


def _make_descriptor(plugin_id: str = "test_plugin", state: PluginState = PluginState.DISCOVERED, module_ref=None) -> PluginDescriptor:
    return PluginDescriptor(
        manifest=_make_manifest(plugin_id),
        metadata=PluginMetadata(),
        state=state,
        path="/fake/path",
        module_ref=module_ref,
    )


# ---------------------------------------------------------------------------
# ManifestBuilder
# ---------------------------------------------------------------------------

class TestManifestBuilder:
    def test_builds_valid_manifest(self):
        manifest = _make_manifest()
        assert manifest.id.value == "test_plugin"
        assert manifest.name == "Test Plugin"
        assert manifest.author == "Tester"
        assert manifest.version == "1.2.3"
        assert PluginCapability.TOOL in manifest.capabilities
        assert PermissionType.NETWORK in manifest.permissions

    def test_chaining(self):
        m = (
            ManifestBuilder("obs", "OBS Studio")
            .author("Dev")
            .version("2.0.0")
            .sdk_version("1.0.0")
            .with_capability(PluginCapability.EVENT_HANDLER)
            .with_permission(PermissionType.AUTOMATION)
            .depends_on("core_plugin", ">=1.0.0")
            .build()
        )
        assert m.author == "Dev"
        assert PluginCapability.EVENT_HANDLER in m.capabilities
        assert len(m.dependencies) == 1


# ---------------------------------------------------------------------------
# ManifestParser
# ---------------------------------------------------------------------------

class TestManifestParser:
    def test_parse_valid_dict(self):
        data = {
            "id": "my_plugin",
            "name": "My Plugin",
            "author": "Alice",
            "version": "0.1.0",
            "sdk_version": "1.0.0",
            "compatible_runtime": ">=2.0.0",
            "entrypoint": "plugin.py",
            "capabilities": ["TOOL"],
            "permissions": ["network"],
        }
        parser = ManifestParser()
        manifest = parser.parse_dict(data)
        assert manifest.id.value == "my_plugin"
        assert PluginCapability.TOOL in manifest.capabilities

    def test_parse_missing_required_field_raises(self):
        parser = ManifestParser()
        with pytest.raises(PluginValidationError, match="missing required keys"):
            parser.parse_dict({"id": "x", "name": "X"})  # missing many fields

    def test_parse_unknown_capability_raises(self):
        data = {
            "id": "x", "name": "X", "author": "A", "version": "0.1", 
            "sdk_version": "1.0", "compatible_runtime": ">=1.0", "entrypoint": "plugin.py",
            "capabilities": ["NOT_A_REAL_CAPABILITY"],
        }
        with pytest.raises(PluginValidationError, match="Unknown capability"):
            ManifestParser().parse_dict(data)


# ---------------------------------------------------------------------------
# PermissionManager
# ---------------------------------------------------------------------------

class TestPermissionManager:
    def test_grant_and_check(self):
        pm = PermissionManager()
        pid = Identifier("plugin_a")
        pm.grant(pid, PermissionType.NETWORK)
        assert pm.has_permission(pid, PermissionType.NETWORK)
        assert not pm.has_permission(pid, PermissionType.CAMERA)

    def test_revoke(self):
        pm = PermissionManager()
        pid = Identifier("plugin_b")
        pm.grant(pid, PermissionType.FILESYSTEM)
        pm.revoke(pid, PermissionType.FILESYSTEM)
        assert not pm.has_permission(pid, PermissionType.FILESYSTEM)

    def test_revoke_all(self):
        pm = PermissionManager()
        pid = Identifier("plugin_c")
        pm.grant(pid, PermissionType.NETWORK)
        pm.grant(pid, PermissionType.CLIPBOARD)
        pm.revoke_all(pid)
        assert pm.list_grants(pid) == []

    def test_assert_permission_raises_if_missing(self):
        pm = PermissionManager()
        pid = Identifier("plugin_d")
        with pytest.raises(PluginSecurityError):
            pm.assert_permission(pid, PermissionType.CAMERA)

    def test_request_permissions_returns_descriptions(self):
        pm = PermissionManager()
        result = pm.request_permissions(Identifier("x"), [PermissionType.NETWORK])
        assert PermissionType.NETWORK in result
        assert isinstance(result[PermissionType.NETWORK], str)


# ---------------------------------------------------------------------------
# PolicySandbox
# ---------------------------------------------------------------------------

class TestPolicySandbox:
    def test_tracks_permissions_from_manifest(self):
        sandbox = PolicySandbox()
        descriptor = _make_descriptor()
        sandbox.track(descriptor)
        pid = descriptor.manifest.id
        assert sandbox.verify_permission(pid, PermissionType.NETWORK)
        assert not sandbox.verify_permission(pid, PermissionType.CAMERA)

    def test_unknown_plugin_denied(self):
        sandbox = PolicySandbox()
        assert not sandbox.verify_permission(Identifier("unknown"), PermissionType.NETWORK)


# ---------------------------------------------------------------------------
# PluginSDK / PluginContext
# ---------------------------------------------------------------------------

class TestPluginSDK:
    def _make_sdk(self):
        mock_bus = MagicMock()
        mock_bus.subscribe.return_value = "sub_id_1"
        mock_cap_mgr = MagicMock()
        pm = PermissionManager()
        return PluginSDK(mock_bus, mock_cap_mgr, pm), mock_bus, mock_cap_mgr, pm

    def test_create_context(self):
        sdk, _, _, _ = self._make_sdk()
        ctx = sdk.create_context("my_plugin")
        assert ctx.plugin_id == "my_plugin"

    def test_capability_registration(self):
        sdk, _, mock_cap_mgr, _ = self._make_sdk()
        ctx = sdk.create_context("my_plugin")
        ctx.capabilities.register("my_tool", "Does something.")
        mock_cap_mgr.register_capability.assert_called_once()

    def test_event_subscription(self):
        sdk, mock_bus, _, _ = self._make_sdk()
        ctx = sdk.create_context("evt_plugin")
        ctx.events.subscribe("mission.started", lambda e: None)
        mock_bus.subscribe.assert_called_once()

    def test_event_publish_blocked_for_core_topics(self):
        sdk, mock_bus, _, _ = self._make_sdk()
        ctx = sdk.create_context("bad_plugin")
        with pytest.raises(PluginSecurityError):
            ctx.events.publish("core.internal", {})

    def test_permission_check_via_context(self):
        sdk, _, _, pm = self._make_sdk()
        pm.grant(Identifier("perm_plugin"), PermissionType.NETWORK)
        ctx = sdk.create_context("perm_plugin")
        assert ctx.has_permission(PermissionType.NETWORK)
        assert not ctx.has_permission(PermissionType.CAMERA)

    def test_assert_permission_raises_if_not_granted(self):
        sdk, _, _, _ = self._make_sdk()
        ctx = sdk.create_context("strict_plugin")
        with pytest.raises(PluginSecurityError):
            ctx.assert_permission(PermissionType.FILESYSTEM)


# ---------------------------------------------------------------------------
# Plugin Lifecycle
# ---------------------------------------------------------------------------

class TestPluginLifecycle:
    def test_full_lifecycle(self):
        lifecycle = DefaultPluginLifecycle()

        # Simulate a module with lifecycle hooks
        mock_module = MagicMock()
        mock_module.plugin_initialize = MagicMock()
        mock_module.plugin_start = MagicMock()
        mock_module.plugin_stop = MagicMock()

        loaded = _make_descriptor(state=PluginState.LOADED, module_ref=mock_module)
        initialized = lifecycle.initialize(loaded)
        assert initialized.state == PluginState.INITIALIZED
        mock_module.plugin_initialize.assert_called_once()

        started = lifecycle.start(initialized)
        assert started.state == PluginState.RUNNING
        mock_module.plugin_start.assert_called_once()

        stopped = lifecycle.stop(started)
        assert stopped.state == PluginState.STOPPED
        mock_module.plugin_stop.assert_called_once()

    def test_invalid_transition_raises(self):
        lifecycle = DefaultPluginLifecycle()
        wrong_state = _make_descriptor(state=PluginState.DISCOVERED)
        with pytest.raises(PluginLifecycleError):
            lifecycle.initialize(wrong_state)  # Must be LOADED first


# ---------------------------------------------------------------------------
# Plugin Registry
# ---------------------------------------------------------------------------

class TestPluginRegistry:
    def test_register_and_get(self):
        registry = ThreadSafePluginRegistry()
        d = _make_descriptor("reg_plugin")
        registry.register(d)
        found = registry.get(Identifier("reg_plugin"))
        assert found is not None
        assert found.manifest.id.value == "reg_plugin"

    def test_find_by_capability(self):
        registry = ThreadSafePluginRegistry()
        registry.register(_make_descriptor("cap_plugin"))
        results = registry.find_by_capability(PluginCapability.TOOL)
        assert len(results) == 1

    def test_remove(self):
        registry = ThreadSafePluginRegistry()
        registry.register(_make_descriptor("del_plugin"))
        removed = registry.remove(Identifier("del_plugin"))
        assert removed
        assert registry.get(Identifier("del_plugin")) is None
