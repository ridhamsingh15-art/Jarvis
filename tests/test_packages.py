import os
import shutil
import tempfile
import zipfile
from unittest.mock import MagicMock

import pytest

from core.events.bus import EventBus
from core.models.primitives import Identifier
from core.packages import (
    AtomicPackageInstaller,
    DefaultDependencyResolver,
    DefaultRollbackManager,
    DependencyError,
    Ed25519SignatureVerifier,
    PackageDependency,
    PackageManager,
    PackageMetadata,
    ThreadSafeLRUCache,
)
from core.runtime.enums import ComponentState


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)

@pytest.fixture
def resolver():
    return DefaultDependencyResolver()

@pytest.fixture
def verifier():
    return Ed25519SignatureVerifier()

@pytest.fixture
def cache():
    return ThreadSafeLRUCache(max_size_bytes=1000)

@pytest.fixture
def installer():
    return AtomicPackageInstaller()

@pytest.fixture
def rollback_manager(temp_dir):
    return DefaultRollbackManager(os.path.join(temp_dir, "backups"))

def test_dependency_resolver(resolver):
    p1 = PackageMetadata(id=Identifier("p1"), version="1", author="A", checksum="c")
    p2 = PackageMetadata(
        id=Identifier("p2"), version="1", author="A", checksum="c",
        dependencies=[PackageDependency(id=Identifier("p1"), version_spec="*")]
    )
    p3 = PackageMetadata(
        id=Identifier("p3"), version="1", author="A", checksum="c",
        dependencies=[PackageDependency(id=Identifier("p2"), version_spec="*")]
    )
    
    resolved = resolver.resolve([p1, p2, p3])
    ids = [p.id.value for p in resolved]
    assert ids == ["p1", "p2", "p3"]
    
    # Missing dependency
    p4 = PackageMetadata(
        id=Identifier("p4"), version="1", author="A", checksum="c",
        dependencies=[PackageDependency(id=Identifier("missing"), version_spec="*")]
    )
    with pytest.raises(DependencyError):
        resolver.resolve([p1, p4])
        
    # Cycle
    c1 = PackageMetadata(
        id=Identifier("c1"), version="1", author="A", checksum="c",
        dependencies=[PackageDependency(id=Identifier("c2"), version_spec="*")]
    )
    c2 = PackageMetadata(
        id=Identifier("c2"), version="1", author="A", checksum="c",
        dependencies=[PackageDependency(id=Identifier("c1"), version_spec="*")]
    )
    with pytest.raises(DependencyError):
        resolver.resolve([c1, c2])

def test_cache(cache, temp_dir):
    f1 = os.path.join(temp_dir, "f1.txt")
    with open(f1, "w") as f:
        f.write("test")
        
    entry = cache.put(Identifier("p1"), "1.0", f1)
    got = cache.get(Identifier("p1"), "1.0")
    assert got is not None
    assert got.package_id == entry.package_id
    assert got.version == entry.version
    assert got.path == entry.path
    
    cache.remove(Identifier("p1"), "1.0")
    assert cache.get(Identifier("p1"), "1.0") is None

def test_rollback(rollback_manager, temp_dir):
    target = os.path.join(temp_dir, "target")
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, "file.txt"), "w") as f:
        f.write("old")
        
    backup_path = rollback_manager.backup_existing(Identifier("p1"), target)
    assert backup_path is not None
    assert not os.path.exists(target)
    
    receipt = rollback_manager.create_receipt(Identifier("p1"), "1.0", backup_path)
    
    # create new target
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, "file.txt"), "w") as f:
        f.write("new")
        
    rollback_manager.rollback(receipt, target)
    
    assert os.path.exists(target)
    with open(os.path.join(target, "file.txt"), "r") as f:
        assert f.read() == "old"

def test_installer(installer, temp_dir, cache):
    # Create dummy zip
    zip_path = os.path.join(temp_dir, "dummy.zip")
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("test.txt", "content")
        
    entry = cache.put(Identifier("p1"), "1.0", zip_path)
    
    target_dir = os.path.join(temp_dir, "installed", "p1")
    installer.install(entry, target_dir)
    
    assert os.path.exists(os.path.join(target_dir, "test.txt"))
    installer.uninstall(Identifier("p1"), target_dir)
    assert not os.path.exists(target_dir)

@pytest.mark.asyncio
async def test_manager_lifecycle(temp_dir):
    logger = MagicMock()
    event_bus = EventBus(logger)
    
    manager = PackageManager(
        repositories=[],
        downloader=MagicMock(),
        resolver=MagicMock(),
        verifier=MagicMock(),
        cache=MagicMock(),
        installer=MagicMock(),
        rollback_manager=MagicMock(),
        event_bus=event_bus,
        logger=logger,
        install_dir=os.path.join(temp_dir, "install")
    )
    
    assert manager.state == ComponentState.INITIALIZED
    await manager.start()
    assert manager.state == ComponentState.RUNNING
    await manager.stop()
    assert manager.state == ComponentState.STOPPED
