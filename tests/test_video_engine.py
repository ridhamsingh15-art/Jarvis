"""
Tests for the AI Content Factory: Video Engine.
"""

import os
from unittest.mock import MagicMock
import pytest

from applications.content_factory.project.models import ProjectBundle, ProjectBundleMetadata
from applications.content_factory.project.manager import ProjectManager
from applications.content_factory.project.asset_manager import AssetManager
from applications.content_factory.project.storage import ProjectStorage
from applications.content_factory.storyboard_engine.models import StoryboardPackage, StoryboardScene
from applications.content_factory.video_engine.manager import VideoEngineManager
from applications.content_factory.video_engine.planner import VideoGenerationPlanner
from applications.content_factory.video_engine.timeline import TimelineBuilder
from applications.content_factory.video_engine.assembler import SceneSequencer
from applications.content_factory.video_engine.ffmpeg_adapter import FFmpegAdapter
from applications.content_factory.video_engine.renderer import VideoRenderer
from applications.content_factory.video_engine.validator import VideoValidator
from applications.content_factory.video_engine.telemetry import VideoEngineTelemetry
from applications.content_factory.video_engine.models import VideoParameters


@pytest.fixture
def video_stack(tmp_path):
    storage = ProjectStorage(root_dir=str(tmp_path))
    asset_manager = AssetManager(storage)
    
    project_manager = ProjectManager(storage, MagicMock(), asset_manager, MagicMock(), MagicMock())
    
    project_dir = storage.get_absolute_path("test_proj", "")
    os.makedirs(project_dir, exist_ok=True)
    
    timeline_builder = TimelineBuilder(project_manager)
    sequencer = SceneSequencer(timeline_builder)
    adapter = FFmpegAdapter()
    renderer = VideoRenderer(adapter)
    validator = VideoValidator()
    telemetry = VideoEngineTelemetry(MagicMock())
    
    planner = VideoGenerationPlanner(
        renderer, sequencer, validator, project_manager, telemetry
    )
    manager = VideoEngineManager(planner, MagicMock(), project_manager)
    return manager, planner, project_dir, project_manager


def test_video_timeline_and_assembly(video_stack):
    manager, planner, project_dir, project_manager = video_stack
    
    # Create mock bundle with animation and voice assets
    bundle = ProjectBundle(
        metadata=ProjectBundleMetadata(
            project_id="test_proj", 
            title="Test",
            tags=[],
            created_at="",
            updated_at=""
        ),
        storyboard_package=StoryboardPackage(
            script_title="Test Script",
            visual_style_override="",
            scenes=[
                StoryboardScene(
                    scene_number=1, narration="", dialogue="", duration=2.0, camera_angle="", camera_movement="",
                    composition="", shot_type="", lighting="", time_of_day="", environment="", location="",
                    characters="", character_positions="", character_expressions="", character_motion="", props="",
                    background="", foreground="", color_palette="", mood="", visual_style="", animation_notes="",
                    transition="crossfade", sound_effects="", music_cue="", voice_timing="", image_prompt="",
                    negative_prompt="", comfyui_prompt="", flux_prompt="", wan_prompt="", thumbnail_candidate=False
                ),
                StoryboardScene(
                    scene_number=2, narration="", dialogue="", duration=2.5, camera_angle="", camera_movement="",
                    composition="", shot_type="", lighting="", time_of_day="", environment="", location="",
                    characters="", character_positions="", character_expressions="", character_motion="", props="",
                    background="", foreground="", color_palette="", mood="", visual_style="", animation_notes="",
                    transition="cut", sound_effects="", music_cue="", voice_timing="", image_prompt="",
                    negative_prompt="", comfyui_prompt="", flux_prompt="", wan_prompt="", thumbnail_candidate=False
                )
            ]
        )
    )
    
    # Mocking physical asset ingestion for the test
    import tempfile
    fd, mock_vid1 = tempfile.mkstemp(suffix=".mp4")
    os.write(fd, b"mock")
    os.close(fd)
    
    fd, mock_vid2 = tempfile.mkstemp(suffix=".mp4")
    os.write(fd, b"mock")
    os.close(fd)
    
    bundle = project_manager.ingest_asset(
        bundle=bundle, source_path=mock_vid1, asset_type="animation", target_directory="animations/scene_001",
        base_filename="clip.mp4", generation_model="mock", scene_number=1
    )
    bundle = project_manager.ingest_asset(
        bundle=bundle, source_path=mock_vid2, asset_type="animation", target_directory="animations/scene_002",
        base_filename="clip.mp4", generation_model="mock", scene_number=2
    )
    
    os.remove(mock_vid1)
    os.remove(mock_vid2)
    
    params = VideoParameters(resolution="1920x1080", fps=24, codec="libx264", bitrate="5M")
    
    # Execute planner
    updated_bundle = planner.execute(bundle, params)
    
    # Verify final video asset exists
    exports_dir = os.path.join(project_dir, "exports")
    assert os.path.exists(exports_dir)
    assert os.path.exists(os.path.join(exports_dir, "video_v1.mp4"))
    assert os.path.exists(os.path.join(exports_dir, "metadata.json"))
    
    # We expect 3 total assets (2 animation + 1 final video)
    assert len(updated_bundle.assets) == 3
    final_video = updated_bundle.assets[-1]
    assert final_video.metadata.asset_type == "video"
    assert final_video.metadata.generation_parameters["resolution"] == "1920x1080"
