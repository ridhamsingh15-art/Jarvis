from dataclasses import dataclass, field

from core.models import JarvisModel
from core.models.primitives import Identifier, Timestamp

from .enums import CacheState, PackageState, RepositoryType


@dataclass(frozen=True, slots=True)
class PackageDependency(JarvisModel):
    """Immutable representation of a package dependency."""
    id: Identifier
    version_spec: str


@dataclass(frozen=True, slots=True)
class PackageMetadata(JarvisModel):
    """Immutable representation of a package's metadata."""
    id: Identifier
    version: str
    author: str
    checksum: str
    signature: str | None = None
    dependencies: list[PackageDependency] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RepositoryConfig(JarvisModel):
    """Immutable representation of a repository configuration."""
    name: str
    url: str
    type: RepositoryType


@dataclass(frozen=True, slots=True)
class InstallationReceipt(JarvisModel):
    """Immutable representation of a completed installation."""
    receipt_id: Identifier
    package_id: Identifier
    version: str
    backup_path: str | None = None
    timestamp: Timestamp = field(default_factory=Timestamp)
    state: PackageState = PackageState.INSTALLED


@dataclass(frozen=True, slots=True)
class PackageCacheEntry(JarvisModel):
    """Immutable representation of a cached package entry."""
    package_id: Identifier
    version: str
    path: str
    state: CacheState = CacheState.VALID
    size: int = 0
    last_accessed: float = 0.0
