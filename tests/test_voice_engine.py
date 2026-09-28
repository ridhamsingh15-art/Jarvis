"""
Tests for the AI Content Factory: Voice Engine.
"""

import os
from unittest.mock import MagicMock
import pytest

from applications.content_factory.project.models import ProjectBundle, ProjectBundleMetadata
from applications.content_factory.project.manager import ProjectManager
from applications.content_factory.project.asset_manager import AssetManager
from applications.content_factory.project.storage import ProjectStorage
from applications.content_factory.storyboard_engine.models import StoryboardPackage, StoryboardScene
from applications.content_factory.voice_engine.manager import VoiceEngineManager
from applications.content_factory.voice_engine.planner import VoiceGenerationPlanner
from applications.content_factory.voice_engine.scheduler import VoiceScheduler
from applications.content_factory.voice_engine.asset_pipeline import VoiceAssetPipeline
from applications.content_factory.voice_engine.renderer import VoiceRenderer
from applications.content_factory.voice_engine.quality import VoiceQualityEvaluator
from applications.content_factory.voice_engine.validator import VoiceValidator
from applications.content_factory.voice_engine.telemetry import VoiceEngineTelemetry


@pytest.fixture
def voice_stack(tmp_path):
    storage = ProjectStorage(root_dir=str(tmp_path))
    asset_manager = AssetManager(storage)
    
    project_manager = ProjectManager(storage, MagicMock(), asset_manager, MagicMock(), MagicMock())
    
    # Initialize the project bundle directory structure using the storage manager
    project_dir = storage.get_absolute_path("test_proj", "")
    os.makedirs(project_dir, exist_ok=True)
    
    renderer = VoiceRenderer()
    evaluator = VoiceQualityEvaluator()
    validator = VoiceValidator()
    pipeline = VoiceAssetPipeline(project_manager)
    scheduler = VoiceScheduler(max_workers=2)
    telemetry = VoiceEngineTelemetry(MagicMock())
    
    planner = VoiceGenerationPlanner(
        renderer, evaluator, validator, pipeline, scheduler, telemetry, max_retries=1
    )
    manager = VoiceEngineManager(planner, MagicMock(), project_manager)
    return manager, planner, pipeline, project_dir


def test_voice_batch_generation(voice_stack):
    manager, planner, pipeline, project_dir = voice_stack
    
    # Create mock bundle
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
                    scene_number=1, narration="Hello world.", dialogue="", duration=2.0, camera_angle="", camera_movement="",
                    composition="", shot_type="", lighting="", time_of_day="", environment="", location="",
                    characters="", character_positions="", character_expressions="", character_motion="", props="",
                    background="", foreground="", color_palette="", mood="dramatic", visual_style="", animation_notes="",
                    transition="", sound_effects="", music_cue="", voice_timing="", image_prompt="",
                    negative_prompt="", comfyui_prompt="", flux_prompt="", wan_prompt="", thumbnail_candidate=False
                )
            ]
        )
    )
    
    # Execute
    updated_bundle = planner.execute_batch(bundle, "piper")
    
    # Verify clip was saved
    scene_dir = os.path.join(project_dir, "voices", "scene_001")
    assert os.path.exists(scene_dir)
    assert os.path.exists(os.path.join(scene_dir, "voice_v1.wav"))
    assert os.path.exists(os.path.join(scene_dir, "metadata.json"))


def test_adapter_failure_and_retries(voice_stack):
    manager, planner, pipeline, project_dir = voice_stack
    
    # Mock renderer to fail first time, succeed second
    call_count = [0]
    def mock_render(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise ValueError("Adapter error")
        return b"MOCK_AUDIO_DATA"
        
    planner._renderer.render = mock_render
    
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
                    scene_number=1, narration="Hello world.", dialogue="", duration=2.0, camera_angle="", camera_movement="",
                    composition="", shot_type="", lighting="", time_of_day="", environment="", location="",
                    characters="", character_positions="", character_expressions="", character_motion="", props="",
                    background="", foreground="", color_palette="", mood="dramatic", visual_style="", animation_notes="",
                    transition="", sound_effects="", music_cue="", voice_timing="", image_prompt="",
                    negative_prompt="", comfyui_prompt="", flux_prompt="", wan_prompt="", thumbnail_candidate=False
                )
            ]
        )
    )
    
    updated_bundle = planner.execute_batch(bundle, "piper")
    assert call_count[0] == 2
    
    scene_dir = os.path.join(project_dir, "voices", "scene_001")
    assert os.path.exists(os.path.join(scene_dir, "voice_v1.wav"))
