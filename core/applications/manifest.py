"""
Manifest Parser for AI Applications.
"""
import logging
from typing import Any
from .models import AppManifest, AppDependency
from .exceptions import InvalidManifestError

logger = logging.getLogger(__name__)

class ManifestParser:
    """Parses and validates application manifests (usually loaded from JSON/YAML)."""

    def parse(self, raw_data: dict[str, Any]) -> AppManifest:
        """Parse raw dictionary data into an AppManifest."""
        logger.debug("Parsing application manifest")
        
        required_fields = ["id", "name", "version", "description", "entry_point"]
        for field in required_fields:
            if field not in raw_data:
                raise InvalidManifestError(f"Missing required field: '{field}'")
                
        dependencies = []
        raw_deps = raw_data.get("dependencies", [])
        if not isinstance(raw_deps, list):
            raise InvalidManifestError("'dependencies' must be a list")
            
        for d in raw_deps:
            if not isinstance(d, dict):
                raise InvalidManifestError("Each dependency must be an object")
            if "name" not in d or "version_range" not in d or "type" not in d:
                raise InvalidManifestError("Dependencies require 'name', 'version_range', and 'type'")
            dependencies.append(AppDependency(
                name=d["name"],
                version_range=d["version_range"],
                type=d["type"]
            ))

        return AppManifest(
            id=raw_data["id"],
            name=raw_data["name"],
            version=raw_data["version"],
            description=raw_data["description"],
            entry_point=raw_data["entry_point"],
            capabilities=raw_data.get("capabilities", []),
            dependencies=dependencies,
            required_permissions=raw_data.get("required_permissions", []),
            storage_requirements=raw_data.get("storage_requirements", {}),
            configuration_schema=raw_data.get("configuration_schema", {})
        )
