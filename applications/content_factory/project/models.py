"""
Data models for the Project Bundle and Asset Manager.
"""

from dataclasses import dataclass, field
from typing import Any

from applications.content_factory.script_engine.models import ScriptPackage
from applications.content_factory.storyboard_engine.models import StoryboardPackage
from core.models import JarvisModel


@dataclass(frozen=True, slots=True)
class AssetMetadata(JarvisModel):
    """Metadata tracking the history and generation parameters of an asset."""
    asset_id: str
    asset_type: str  # e.g. "image", "audio", "video", "subtitle"
    created_at: str
    version: int
    generation_model: str
    generation_parameters: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)  # asset_ids this asset depends on


@dataclass(frozen=True, slots=True)
class Asset(JarvisModel):
    """A tracked digital asset within a project."""
    metadata: AssetMetadata
    relative_path: str  # Path relative to project root
    scene_number: int | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ProjectBundleMetadata(JarvisModel):
    """Top-level metadata for the Project Bundle."""
    project_id: str
    title: str
    tags: list[str]
    created_at: str
    updated_at: str
    status: str = "draft"  # draft, in_production, exported, archived
    publishing_status: str = "unpubished" # unpublished, scheduled, published
    seo_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProjectBundle(JarvisModel):
    """The aggregate root of a content production project."""
    metadata: ProjectBundleMetadata
    script_package: ScriptPackage | None = None
    storyboard_package: StoryboardPackage | None = None
    assets: list[Asset] = field(default_factory=list)
    mission_history: list[str] = field(default_factory=list)  # list of mission IDs
    analytics: dict[str, Any] = field(default_factory=dict)
