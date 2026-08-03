import os
import shutil
import uuid

from core.models.primitives import Identifier

from .exceptions import RollbackError
from .interfaces import RollbackManager
from .models import InstallationReceipt


class DefaultRollbackManager(RollbackManager):
    """Manages installation receipts and performs rollbacks."""

    def __init__(self, backup_dir: str) -> None:
        self._backup_dir = backup_dir
        os.makedirs(self._backup_dir, exist_ok=True)
        self._receipts: dict[str, InstallationReceipt] = {}

    def create_receipt(self, package_id: Identifier, version: str, backup_path: str | None = None) -> InstallationReceipt:
        receipt = InstallationReceipt(
            receipt_id=Identifier(str(uuid.uuid4())),
            package_id=package_id,
            version=version,
            backup_path=backup_path
        )
        self._receipts[package_id.value] = receipt
        return receipt

    def get_receipt(self, package_id: Identifier) -> InstallationReceipt | None:
        return self._receipts.get(package_id.value)

    def rollback(self, receipt: InstallationReceipt, target_dir: str) -> None:
        if not receipt.backup_path or not os.path.exists(receipt.backup_path):
            raise RollbackError(f"Backup for {receipt.package_id.value} not found or invalid.")

        try:
            # If a broken new version exists at target_dir, remove it
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)

            # Restore the backup
            os.rename(receipt.backup_path, target_dir)
            
            # Remove receipt since we rolled back
            if receipt.package_id.value in self._receipts:
                del self._receipts[receipt.package_id.value]
                
        except Exception as e:  # noqa: BLE001
            raise RollbackError(f"Failed to rollback {receipt.package_id.value}: {e}")

    def backup_existing(self, package_id: Identifier, target_dir: str) -> str | None:
        """Helper to create a backup before an upgrade."""
        if not os.path.exists(target_dir):
            return None
            
        backup_path = os.path.join(self._backup_dir, f"{package_id.value}_backup_{uuid.uuid4().hex}")
        try:
            os.rename(target_dir, backup_path)
            return backup_path
        except Exception as e:  # noqa: BLE001
            raise RollbackError(f"Failed to backup {package_id.value}: {e}")
