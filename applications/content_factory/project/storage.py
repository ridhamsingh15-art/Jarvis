"""
Disk storage abstraction for Project Bundles.
"""

import json
import shutil
from pathlib import Path

from .exceptions import StorageError
from .models import ProjectBundle


class ProjectStorage:
    """Handles all POSIX file I/O for Project Bundles."""

    REQUIRED_DIRS = [
        "prompts",
        "images",
        "animations",
        "voices",
        "music",
        "subtitles",
        "thumbnails",
        "exports",
        "analytics",
    ]

    def __init__(self, root_dir: str) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def initialize_project_directory(self, project_id: str) -> Path:
        """Creates the directory structure for a new project."""
        try:
            proj_dir = self.root_dir / project_id
            proj_dir.mkdir(parents=True, exist_ok=True)
            for d in self.REQUIRED_DIRS:
                (proj_dir / d).mkdir(exist_ok=True)
            return proj_dir
        except Exception as e:
            raise StorageError(f"Failed to initialize project directory for {project_id}: {e}") from e

    def save_bundle(self, bundle: ProjectBundle) -> None:
        """Serializes and saves the ProjectBundle to disk."""
        try:
            proj_dir = self.root_dir / bundle.metadata.project_id
            if not proj_dir.exists():
                self.initialize_project_directory(bundle.metadata.project_id)

            import dataclasses
            
            # Save the main project.json
            bundle_dict = dataclasses.asdict(bundle)
            
            # We don't want to duplicate the massive script/storyboard payloads in project.json if they exist
            # So we strip them from the main file and save them separately
            bundle_dict.pop("script_package", None)
            bundle_dict.pop("storyboard_package", None)
            
            with open(proj_dir / "project.json", "w", encoding="utf-8") as f:
                json.dump(bundle_dict, f, indent=2)

            # Save Script
            if bundle.script_package:
                with open(proj_dir / "script.json", "w", encoding="utf-8") as f:
                    json.dump(dataclasses.asdict(bundle.script_package), f, indent=2)

            # Save Storyboard
            if bundle.storyboard_package:
                with open(proj_dir / "storyboard.json", "w", encoding="utf-8") as f:
                    json.dump(dataclasses.asdict(bundle.storyboard_package), f, indent=2)
                    
        except Exception as e:
            raise StorageError(f"Failed to save bundle {bundle.metadata.project_id}: {e}") from e

    def load_bundle(self, project_id: str) -> ProjectBundle | None:
        """Loads a ProjectBundle from disk."""
        proj_dir = self.root_dir / project_id
        if not proj_dir.exists() or not (proj_dir / "project.json").exists():
            return None

        try:
            with open(proj_dir / "project.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Attempt to load script and storyboard if they exist
            script_package = None
            script_file = proj_dir / "script.json"
            if script_file.exists():
                with open(script_file, "r", encoding="utf-8") as f:
                    script_data = json.load(f)
                    from applications.content_factory.script_engine.formatter import (
                        format_script,
                    )
                    try:
                        script_package = format_script(script_data)
                    except Exception:
                        pass
                        
            storyboard_package = None
            storyboard_file = proj_dir / "storyboard.json"
            if storyboard_file.exists():
                with open(storyboard_file, "r", encoding="utf-8") as f:
                    sb_data = json.load(f)
                    from applications.content_factory.storyboard_engine.formatter import (
                        format_storyboard,
                    )
                    try:
                        storyboard_package = format_storyboard(sb_data)
                    except Exception:
                        pass
            
            # Hydrate Models
            from .models import Asset, AssetMetadata, ProjectBundleMetadata
            
            assets = []
            for a_data in data.get("assets", []):
                meta = AssetMetadata(**a_data["metadata"])
                a_data["metadata"] = meta
                assets.append(Asset(**a_data))
                
            meta_data = data["metadata"]
            metadata = ProjectBundleMetadata(**meta_data)
            
            return ProjectBundle(
                metadata=metadata,
                script_package=script_package,
                storyboard_package=storyboard_package,
                assets=assets,
                mission_history=data.get("mission_history", []),
                analytics=data.get("analytics", {})
            )
            
        except Exception as e:
            raise StorageError(f"Failed to load bundle {project_id}: {e}") from e

    def store_asset_file(self, project_id: str, source_path: str, relative_destination: str) -> str:
        """Moves a binary file into the project bundle directory."""
        try:
            dest = self.root_dir / project_id / relative_destination
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, str(dest))
            return relative_destination
        except Exception as e:
            raise StorageError(f"Failed to store asset file {source_path} to {relative_destination}: {e}") from e

    def get_absolute_path(self, project_id: str, relative_path: str) -> str:
        return str(self.root_dir / project_id / relative_path)
