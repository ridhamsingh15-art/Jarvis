"""
Logic for file and asset versioning.
"""

import re
from pathlib import Path


class VersioningUtil:
    """Utility methods for parsing and incrementing file version strings."""

    _VERSION_REGEX = re.compile(r"^(.*?)(_v(\d+))?(\.[a-zA-Z0-9]+)?$")

    @classmethod
    def get_next_versioned_path(cls, base_path: str, existing_paths: list[str]) -> tuple[str, int]:
        """
        Determines the next available versioned filename for a given base path.
        e.g., if scene_1.png exists, returns (scene_1_v2.png, 2).
        If base doesn't exist, returns (scene_1_v1.png, 1) or just assumes base is v1.
        For simplicity, we'll enforce that the first is v1.
        """
        base = Path(base_path)
        stem = base.stem
        ext = base.suffix
        
        # Remove any existing version tag from the stem to find the true base
        match = cls._VERSION_REGEX.match(base.name)
        if match:
            true_stem = match.group(1)
        else:
            true_stem = stem

        highest_version = 0
        
        # Check all existing paths that match the true_stem
        for existing in existing_paths:
            epath = Path(existing)
            if epath.suffix == ext:
                ematch = cls._VERSION_REGEX.match(epath.name)
                if ematch and ematch.group(1) == true_stem:
                    v_str = ematch.group(3)
                    v = int(v_str) if v_str else 1
                    highest_version = max(highest_version, v)

        next_v = highest_version + 1
        new_name = f"{true_stem}_v{next_v}{ext}"
        new_path = str(base.parent / new_name).replace("\\", "/")
        
        return new_path, next_v
