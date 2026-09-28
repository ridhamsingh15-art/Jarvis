"""
Tests for the Post-Production Pipeline.
"""
import pytest
import dataclasses
from pathlib import Path

from applications.content_factory.project.models import ProjectBundle, ProjectBundleMetadata
from applications.content_factory.project.manager import ProjectManager
from applications.content_factory.storyboard_engine.models import StoryboardPackage, StoryboardScene
from core.events.bus import EventBus
from core.mission.manager import MissionManager

from applications.content_factory.music_engine.planner import MusicGenerationPlanner
from applications.content_factory.music_engine.generator import MusicGenerator
from applications.content_factory.music_engine.telemetry import MusicEngineTelemetry

from applications.content_factory.subtitle_engine.planner import SubtitleGenerationPlanner
from applications.content_factory.subtitle_engine.generator import SubtitleGenerator
from applications.content_factory.subtitle_engine.telemetry import SubtitleEngineTelemetry

from applications.content_factory.thumbnail_engine.planner import ThumbnailGenerationPlanner
from applications.content_factory.thumbnail_engine.generator import ThumbnailGenerator
from applications.content_factory.thumbnail_engine.telemetry import ThumbnailEngineTelemetry

from applications.content_factory.seo_engine.planner import SEOGenerationPlanner
from applications.content_factory.seo_engine.generator import SEOGenerator
from applications.content_factory.seo_engine.telemetry import SEOEngineTelemetry

from applications.content_factory.publishing_engine.planner import PublishingPlanner
from applications.content_factory.publishing_engine.adapter import PublishingAdapter
from applications.content_factory.publishing_engine.models import PublishRequest
from applications.content_factory.publishing_engine.telemetry import PublishingEngineTelemetry

from applications.content_factory.analytics_engine.planner import AnalyticsPlanner
from applications.content_factory.analytics_engine.tracker import AnalyticsTracker
from applications.content_factory.analytics_engine.models import AnalyticsSyncRequest
from applications.content_factory.analytics_engine.telemetry import AnalyticsEngineTelemetry


@pytest.fixture
def event_bus():
    from core.telemetry.logger import AsyncLogger
    from core.telemetry.levels import LogLevel
    from unittest.mock import MagicMock
    
    dummy_masker = MagicMock()
    dummy_masker.mask.side_effect = lambda x: x
    logger = AsyncLogger(level=LogLevel.INFO, masker=dummy_masker, outputs=[])
    return EventBus(logger=logger)

@pytest.fixture
def project_manager(tmp_path, event_bus):
    from applications.content_factory.project.storage import ProjectStorage
    from applications.content_factory.project.registry import ProjectRegistry
    from applications.content_factory.project.asset_manager import AssetManager
    from applications.content_factory.project.validator import ProjectValidator
    from applications.content_factory.project.telemetry import ProjectManagerTelemetry
    
    storage = ProjectStorage(root_dir=str(tmp_path))
    registry = ProjectRegistry(storage)
    asset_manager = AssetManager(storage)
    validator = ProjectValidator(storage)
    telemetry = ProjectManagerTelemetry(event_bus)
    
    return ProjectManager(storage, registry, asset_manager, validator, telemetry)


@pytest.fixture
def mock_n8n_runner():
    class MockRunner:
        def run_workflow(self, name, payload):
            class MockResult:
                success = True
            return MockResult()
    return MockRunner()


@pytest.fixture
def mock_bundle(project_manager: ProjectManager):
    bundle = project_manager.create_project("Test Post-Production Project", ["test"])
    
    scene = StoryboardScene(
        scene_number=1,
        narration="Hello world.",
        dialogue="",
        duration=5.0,
        camera_angle="wide",
        camera_movement="pan",
        composition="center",
        shot_type="wide",
        lighting="bright",
        time_of_day="day",
        environment="outside",
        location="park",
        characters=[],
        character_positions="",
        character_expressions="",
        character_motion="",
        props=[],
        background="",
        foreground="",
        color_palette=[],
        mood="neutral",
        visual_style="realistic",
        animation_notes="",
        transition="cut",
        sound_effects="",
        music_cue="",
        voice_timing="",
        image_prompt="A test scene",
        negative_prompt=""
    )
    
    sb_package = StoryboardPackage(
        script_title="Test Project",
        visual_style_override="realistic",
        scenes=[scene]
    )
    
    # Inject storyboard package
    bundle = dataclasses.replace(bundle, storyboard_package=sb_package)
    
    # Inject a mock image asset for thumbnail engine
    import tempfile
    import os
    fd, temp_path = tempfile.mkstemp(suffix=".jpg")
    os.write(fd, b"MOCK_IMAGE_DATA")
    os.close(fd)
    
    bundle = project_manager.ingest_asset(
        bundle=bundle,
        source_path=temp_path,
        asset_type="image",
        target_directory="images",
        base_filename="mock.jpg",
        generation_model="mock",
        generation_parameters={},
        dependencies=[],
        scene_number=1,
        tags=[]
    )
    os.remove(temp_path)
    
    return bundle


def test_music_engine_planner(mock_bundle, project_manager, event_bus):
    planner = MusicGenerationPlanner(
        MusicGenerator(), project_manager, MusicEngineTelemetry(event_bus)
    )
    
    updated = planner.execute(mock_bundle)
    assert len(updated.assets) == 2  # mock image + new music
    assert updated.assets[-1].metadata.asset_type == "music"
    assert updated.assets[-1].relative_path.endswith("background_v1.wav")


def test_subtitle_engine_planner(mock_bundle, project_manager, event_bus):
    planner = SubtitleGenerationPlanner(
        SubtitleGenerator(), project_manager, SubtitleEngineTelemetry(event_bus)
    )
    
    updated = planner.execute(mock_bundle)
    assert len(updated.assets) == 2
    assert updated.assets[-1].metadata.asset_type == "subtitle"
    assert updated.assets[-1].relative_path.endswith("subs_v1.srt")


def test_thumbnail_engine_planner(mock_bundle, project_manager, event_bus):
    planner = ThumbnailGenerationPlanner(
        ThumbnailGenerator(), project_manager, ThumbnailEngineTelemetry(event_bus)
    )
    
    updated = planner.execute(mock_bundle)
    assert len(updated.assets) == 2
    assert updated.assets[-1].metadata.asset_type == "thumbnail"
    assert updated.assets[-1].relative_path.endswith("thumbnail_v1.jpg")


def test_seo_engine_planner(mock_bundle, project_manager, event_bus):
    planner = SEOGenerationPlanner(
        SEOGenerator(), project_manager, SEOEngineTelemetry(event_bus)
    )
    
    updated = planner.execute(mock_bundle)
    assert len(updated.assets) == 2
    assert updated.assets[-1].metadata.asset_type == "seo"
    assert updated.metadata.seo_metadata["youtube_title"] == "Test Project | Animated Short"


def test_publishing_engine_planner(mock_bundle, project_manager, event_bus, mock_n8n_runner):
    # Setup mock SEO
    mock_bundle = dataclasses.replace(
        mock_bundle,
        metadata=dataclasses.replace(mock_bundle.metadata, seo_metadata={"youtube_title": "Test Project"})
    )
    
    planner = PublishingPlanner(
        PublishingAdapter(mock_n8n_runner), project_manager, PublishingEngineTelemetry(event_bus)
    )
    
    request = PublishRequest(platforms=["youtube"], mode="immediate")
    updated = planner.execute(mock_bundle, request)
    assert updated.metadata.publishing_status == "published"


def test_analytics_engine_planner(mock_bundle, project_manager, event_bus):
    # Setup publish status
    mock_bundle = dataclasses.replace(
        mock_bundle,
        metadata=dataclasses.replace(mock_bundle.metadata, publishing_status="published")
    )
    
    planner = AnalyticsPlanner(
        AnalyticsTracker(), project_manager, AnalyticsEngineTelemetry(event_bus)
    )
    
    request = AnalyticsSyncRequest(platforms=["youtube"], days_since_publish=1)
    updated = planner.execute(mock_bundle, request)
    assert updated.analytics["views"] == 1500
