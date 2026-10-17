"""
Integrity validation for Project Bundles.
"""

from pathlib import Path

from .exceptions import ProjectValidationError
from .models import ProjectBundle
from .storage import ProjectStorage


class ProjectValidator:
    """Ensures structural and referential integrity of a ProjectBundle."""

    def __init__(self, storage: ProjectStorage) -> None:
        self._storage = storage

    def validate(self, bundle: ProjectBundle) -> None:
        """
        Validates the project bundle.
        Checks:
        - Metadata is populated.
        - Physical files referenced in Assets actually exist.
        """
        errors = []
        
        if not bundle.metadata.project_id:
            errors.append("Project ID is missing.")
            
        project_dir = Path(self._storage.get_absolute_path(bundle.metadata.project_id, ""))
        
        for asset in bundle.assets:
            expected_path = project_dir / asset.relative_path
            if not expected_path.exists():
                errors.append(f"Asset {asset.metadata.asset_id} references a missing file: {asset.relative_path}")
                
            if asset.metadata.version < 1:
                errors.append(f"Asset {asset.metadata.asset_id} has invalid version {asset.metadata.version}")
                
        if errors:
            raise ProjectValidationError("Project bundle validation failed:\n- " + "\n- ".join(errors))
