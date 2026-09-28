"""
Tests for the AI Content Factory: Project Bundle & Asset Manager.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from applications.content_factory.project.asset_manager import AssetManager
from applications.content_factory.project.bundle import BundleModifier
from applications.content_factory.project.exceptions import ProjectValidationError
from applications.content_factory.project.manager import ProjectManager
from applications.content_factory.project.registry import ProjectRegistry
from applications.content_factory.project.storage import ProjectStorage
from applications.content_factory.project.telemetry import ProjectManagerTelemetry
from applications.content_factory.project.validator import ProjectValidator
from applications.content_factory.project.versioning import VersioningUtil


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def pm_stack(temp_workspace):
    storage = ProjectStorage(root_dir=str(Path(temp_workspace) / "projects"))
    registry = ProjectRegistry(storage)
    asset_manager = AssetManager(storage)
    validator = ProjectValidator(storage)
    telemetry = ProjectManagerTelemetry(MagicMock())
    
    manager = ProjectManager(storage, registry, asset_manager, validator, telemetry)
    return manager, storage


def test_versioning_util():
    paths = []
    # Test first file
    new_path, version = VersioningUtil.get_next_versioned_path("scene_1.png", paths)
    assert new_path == "scene_1_v1.png"
    assert version == 1
    
    paths.append("scene_1_v1.png")
    
    # Test second file
    new_path, version = VersioningUtil.get_next_versioned_path("scene_1.png", paths)
    assert new_path == "scene_1_v2.png"
    assert version == 2
    
    paths.append("scene_1_v2.png")
    paths.append("scene_1_v3.png")
    
    # Test jumping versions
    new_path, version = VersioningUtil.get_next_versioned_path("scene_1_v2.png", paths)
    assert new_path == "scene_1_v4.png"
    assert version == 4


def test_project_creation(pm_stack):
    manager, storage = pm_stack
    bundle = manager.create_project(title="Test Project", tags=["test"])
    
    assert bundle.metadata.title == "Test Project"
    assert bundle.metadata.status == "draft"
    
    # Verify directory structure
    proj_dir = storage.root_dir / bundle.metadata.project_id
    assert proj_dir.exists()
    assert (proj_dir / "images").exists()
    assert (proj_dir / "prompts").exists()
    assert (proj_dir / "project.json").exists()


def test_asset_ingestion(pm_stack, temp_workspace):
    manager, storage = pm_stack
    bundle = manager.create_project(title="Asset Project")
    
    # Create a dummy file to ingest
    dummy_file = Path(temp_workspace) / "dummy.png"
    dummy_file.write_text("dummy content")
    
    updated_bundle = manager.ingest_asset(
        bundle=bundle,
        source_path=str(dummy_file),
        asset_type="image",
        target_directory="images",
        base_filename="scene_1.png",
        generation_model="flux",
        scene_number=1,
        tags=["epic"]
    )
    
    assert len(updated_bundle.assets) == 1
    asset = updated_bundle.assets[0]
    
    assert asset.metadata.version == 1
    assert asset.relative_path == "images/scene_1_v1.png"
    
    # Ingest again to test version increment
    updated_bundle_v2 = manager.ingest_asset(
        bundle=updated_bundle,
        source_path=str(dummy_file),
        asset_type="image",
        target_directory="images",
        base_filename="scene_1.png",
        generation_model="flux"
    )
    
    assert len(updated_bundle_v2.assets) == 2
    asset_v2 = updated_bundle_v2.assets[1]
    
    assert asset_v2.metadata.version == 2
    assert asset_v2.relative_path == "images/scene_1_v2.png"
    
    # Verify disk
    proj_dir = storage.root_dir / bundle.metadata.project_id
    assert (proj_dir / "images" / "scene_1_v1.png").exists()
    assert (proj_dir / "images" / "scene_1_v2.png").exists()


def test_validation_failure(pm_stack):
    manager, _ = pm_stack
    bundle = manager.create_project(title="Validation Project")
    
    # Manually add an asset without putting a file on disk
    from applications.content_factory.project.models import Asset, AssetMetadata
    bad_meta = AssetMetadata(asset_id="123", asset_type="image", created_at="", version=1, generation_model="")
    bad_asset = Asset(metadata=bad_meta, relative_path="images/missing.png")
    
    bad_bundle = BundleModifier.add_asset(bundle, bad_asset)
    
    with pytest.raises(ProjectValidationError):
        manager.save_project(bad_bundle)


def test_registry_search(pm_stack):
    manager, _ = pm_stack
    manager.create_project(title="Ramayana Ep 1", tags=["mythology", "episode_1"])
    manager.create_project(title="Mahabharata Ep 1", tags=["mythology", "episode_1"])
    manager.create_project(title="Python Tutorial", tags=["coding"])
    
    # Search by title
    results = manager.search_projects(title="ramayana")
    assert len(results) == 1
    
    # Search by tag
    results = manager.search_projects(tag="mythology")
    assert len(results) == 2
    
    results = manager.search_projects(tag="coding")
    assert len(results) == 1


def test_storage_reload(pm_stack, temp_workspace):
    manager, storage = pm_stack
    bundle = manager.create_project(title="Reload Project")
    
    # Save a dummy asset
    dummy_file = Path(temp_workspace) / "dummy.png"
    dummy_file.write_text("dummy content")
    bundle = manager.ingest_asset(
        bundle=bundle,
        source_path=str(dummy_file),
        asset_type="image",
        target_directory="images",
        base_filename="test.png",
        generation_model="flux"
    )
    
    # New registry/manager instance pointing to same storage
    registry_2 = ProjectRegistry(storage)
    registry_2.scan()
    
    assert len(registry_2.list_all()) == 1
    
    reloaded_metadata = registry_2.find_by_title("Reload Project")[0]
    reloaded_bundle = storage.load_bundle(reloaded_metadata.project_id)
    
    assert reloaded_bundle is not None
    assert len(reloaded_bundle.assets) == 1
    assert reloaded_bundle.assets[0].relative_path == "images/test_v1.png"
