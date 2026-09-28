from unittest.mock import MagicMock

import pytest

from core.events.bus import EventBus
from core.models.primitives import Identifier
from core.plugins import (
    DefaultPluginLifecycle,
    DefaultPluginValidator,
    DynamicPluginLoader,
    FileSystemPluginDiscoverer,
    PluginDependency,
    PluginDependencyError,
    PluginDescriptor,
    PluginManager,
    PluginManifest,
    PluginMetadata,
    PluginState,
    PluginValidationError,
    PolicySandbox,
    ThreadSafePluginRegistry,
)
from core.runtime.enums import ComponentState


@pytest.fixture
def registry():
    return ThreadSafePluginRegistry()

@pytest.fixture
def validator():
    return DefaultPluginValidator("1.0.0", "jarvis-runtime")

@pytest.fixture
def discoverer():
    return FileSystemPluginDiscoverer()

@pytest.fixture
def loader():
    return DynamicPluginLoader()

@pytest.fixture
def sandbox():
    return PolicySandbox()

@pytest.fixture
def lifecycle():
    return DefaultPluginLifecycle()

@pytest.fixture
def event_bus():
    logger = MagicMock()
    return EventBus(logger)

@pytest.fixture
def manager(discoverer, validator, loader, sandbox, lifecycle, registry, event_bus):
    logger = MagicMock()
    return PluginManager(
        discoverer, validator, loader, sandbox, lifecycle, registry, event_bus, logger, "test_plugins_dir"
    )

def test_registry(registry):
    manifest = PluginManifest(
        id=Identifier("test_plugin"),
        name="Test",
        author="Author",
        version="1.0",
        sdk_version="1.0",
        compatible_runtime="jarvis",
        entrypoint="main.py"
    )
    descriptor = PluginDescriptor(
        manifest=manifest,
        metadata=PluginMetadata(),
        state=PluginState.DISCOVERED,
        path="/tmp"
    )
    
    registry.register(descriptor)
    assert registry.exists(Identifier("test_plugin"))
    assert len(registry.list()) == 1
    
    fetched = registry.get(Identifier("test_plugin"))
    assert fetched.manifest.name == "Test"
    
    registry.remove(Identifier("test_plugin"))
    assert len(registry.list()) == 0

def test_validator_manifest(validator):
    manifest = PluginManifest(
        id=Identifier("test"),
        name="Test",
        author="Author",
        version="1.0",
        sdk_version="1.0.0",
        compatible_runtime="jarvis-runtime",
        entrypoint="main.py"
    )
    # Valid
    assert validator.validate_manifest(manifest) is True

    # Invalid runtime
    bad_manifest = PluginManifest(
        id=Identifier("test2"),
        name="Test",
        author="Author",
        version="1.0",
        sdk_version="1.0.0",
        compatible_runtime="other-runtime",
        entrypoint="main.py"
    )
    with pytest.raises(PluginValidationError):
        validator.validate_manifest(bad_manifest)

def test_validator_graph(validator):
    manifest1 = PluginManifest(
        id=Identifier("p1"),
        name="P1",
        author="A",
        version="1.0",
        sdk_version="1.0.0",
        compatible_runtime="jarvis-runtime",
        entrypoint="m1.py"
    )
    manifest2 = PluginManifest(
        id=Identifier("p2"),
        name="P2",
        author="A",
        version="1.0",
        sdk_version="1.0.0",
        compatible_runtime="jarvis-runtime",
        entrypoint="m2.py",
        dependencies=[PluginDependency(id=Identifier("p1"), version_spec="*")]
    )
    
    d1 = PluginDescriptor(manifest=manifest1, metadata=PluginMetadata(), state=PluginState.DISCOVERED, path="/tmp")
    d2 = PluginDescriptor(manifest=manifest2, metadata=PluginMetadata(), state=PluginState.DISCOVERED, path="/tmp")
    
    assert validator.validate_graph([d1, d2]) is True
    
    # Missing dependency
    manifest3 = PluginManifest(
        id=Identifier("p3"),
        name="P3",
        author="A",
        version="1.0",
        sdk_version="1.0.0",
        compatible_runtime="jarvis-runtime",
        entrypoint="m3.py",
        dependencies=[PluginDependency(id=Identifier("missing"), version_spec="*")]
    )
    d3 = PluginDescriptor(manifest=manifest3, metadata=PluginMetadata(), state=PluginState.DISCOVERED, path="/tmp")
    
    with pytest.raises(PluginDependencyError):
        validator.validate_graph([d1, d3])

    # Cyclic dependency
    manifest_cycle_1 = PluginManifest(
        id=Identifier("c1"),
        name="C1",
        author="A",
        version="1.0",
        sdk_version="1.0.0",
        compatible_runtime="jarvis-runtime",
        entrypoint="c1.py",
        dependencies=[PluginDependency(id=Identifier("c2"), version_spec="*")]
    )
    manifest_cycle_2 = PluginManifest(
        id=Identifier("c2"),
        name="C2",
        author="A",
        version="1.0",
        sdk_version="1.0.0",
        compatible_runtime="jarvis-runtime",
        entrypoint="c2.py",
        dependencies=[PluginDependency(id=Identifier("c1"), version_spec="*")]
    )
    dc1 = PluginDescriptor(manifest=manifest_cycle_1, metadata=PluginMetadata(), state=PluginState.DISCOVERED, path="/tmp")
    dc2 = PluginDescriptor(manifest=manifest_cycle_2, metadata=PluginMetadata(), state=PluginState.DISCOVERED, path="/tmp")
    
    with pytest.raises(PluginDependencyError):
        validator.validate_graph([dc1, dc2])

def test_sandbox(sandbox):
    manifest = PluginManifest(
        id=Identifier("test_sandbox"),
        name="TS",
        author="A",
        version="1.0",
        sdk_version="1.0.0",
        compatible_runtime="jarvis",
        entrypoint="main.py",
        permissions=["network.read", "fs.read"]
    )
    d = PluginDescriptor(manifest=manifest, metadata=PluginMetadata(), state=PluginState.DISCOVERED, path="/tmp")
    sandbox.track(d)
    
    assert sandbox.verify_permission(Identifier("test_sandbox"), "network.read") is True
    assert sandbox.verify_permission(Identifier("test_sandbox"), "fs.write") is False

@pytest.mark.asyncio
async def test_manager_lifecycle(manager):
    assert manager.state == ComponentState.INITIALIZED
    
    await manager.start()
    assert manager.state == ComponentState.RUNNING
    
    await manager.stop()
    assert manager.state == ComponentState.STOPPED
