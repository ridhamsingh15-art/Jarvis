import os
import shutil
import tempfile
import zipfile

from core.models.primitives import Identifier

from .exceptions import InstallError
from .interfaces import PackageInstaller
from .models import PackageCacheEntry


class AtomicPackageInstaller(PackageInstaller):
    """Installs packages atomically using temporary directories."""

    def install(self, cache_entry: PackageCacheEntry, target_dir: str) -> None:
        if not os.path.exists(cache_entry.path):
            raise InstallError(f"Cached archive not found at {cache_entry.path}")

        # Create a secure temporary directory next to the target for atomic rename
        base_target_dir = os.path.dirname(target_dir)
        os.makedirs(base_target_dir, exist_ok=True)
        
        temp_dir = tempfile.mkdtemp(dir=base_target_dir, prefix=".tmp-install-")
        
        try:
            # Extract to temp
            with zipfile.ZipFile(cache_entry.path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Atomic swap
            if os.path.exists(target_dir):
                # For an atomic update, the caller should have backed it up and removed it.
                # If it's still here, we remove it to allow rename (on windows rename fails if dest exists).
                shutil.rmtree(target_dir)
                
            os.rename(temp_dir, target_dir)
        except Exception as e:  # noqa: BLE001
            # Clean up temp
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise InstallError(f"Installation of {cache_entry.package_id.value} failed: {e}")

    def uninstall(self, package_id: Identifier, target_dir: str) -> None:
        if os.path.exists(target_dir):
            try:
                shutil.rmtree(target_dir)
            except Exception as e:  # noqa: BLE001
                raise InstallError(f"Failed to uninstall {package_id.value}: {e}")
