import builtins
from abc import ABC, abstractmethod

from core.models.primitives import Identifier

from .models import (
    InstallationReceipt,
    PackageCacheEntry,
    PackageMetadata,
    RepositoryConfig,
)


class PackageRepository(ABC):
    """Abstract interface for querying package repositories."""

    @abstractmethod
    def fetch_metadata(self, package_id: Identifier, version: str | None = None) -> PackageMetadata:
        pass


class PackageDownloader(ABC):
    """Abstract interface for downloading package archives."""

    @abstractmethod
    def download(self, metadata: PackageMetadata, repository: RepositoryConfig, target_path: str) -> str:
        pass


class DependencyResolver(ABC):
    """Abstract interface for resolving dependency graphs."""

    @abstractmethod
    def resolve(self, packages: builtins.list[PackageMetadata]) -> builtins.list[PackageMetadata]:
        pass


class SignatureVerifier(ABC):
    """Abstract interface for validating cryptographic signatures and checksums."""

    @abstractmethod
    def verify(self, file_path: str, metadata: PackageMetadata) -> bool:
        pass


class PackageCache(ABC):
    """Abstract interface for managing cached packages."""

    @abstractmethod
    def get(self, package_id: Identifier, version: str) -> PackageCacheEntry | None:
        pass

    @abstractmethod
    def put(self, package_id: Identifier, version: str, file_path: str) -> PackageCacheEntry:
        pass
        
    @abstractmethod
    def remove(self, package_id: Identifier, version: str) -> bool:
        pass


class PackageInstaller(ABC):
    """Abstract interface for atomic package installation."""

    @abstractmethod
    def install(self, cache_entry: PackageCacheEntry, target_dir: str) -> None:
        pass

    @abstractmethod
    def uninstall(self, package_id: Identifier, target_dir: str) -> None:
        pass


class RollbackManager(ABC):
    """Abstract interface for managing installation receipts and rollbacks."""

    @abstractmethod
    def create_receipt(self, package_id: Identifier, version: str, backup_path: str | None = None) -> InstallationReceipt:
        pass

    @abstractmethod
    def get_receipt(self, package_id: Identifier) -> InstallationReceipt | None:
        pass

    @abstractmethod
    def rollback(self, receipt: InstallationReceipt, target_dir: str) -> None:
        pass
