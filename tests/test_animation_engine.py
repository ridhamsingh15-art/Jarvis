"""
Tests for the AI Content Factory: Animation Engine.
"""

import os
from unittest.mock import MagicMock
import pytest
import shutil

from applications.content_factory.project.models import ProjectBundle, ProjectBundleMetadata
from applications.content_factory.project.manager import ProjectManager
from applications.content_factory.project.asset_manager import AssetManager
from applications.content_factory.project.storage import ProjectStorage
from applications.content_factory.storyboard_engine.models import StoryboardPackage, StoryboardScene
from applications.content_factory.animation_engine.manager import AnimationEngineManager
from applications.content_factory.animation_engine.planner import AnimationGenerationPlanner
from applications.content_factory.animation_engine.scheduler import AnimationScheduler
from applications.content_factory.animation_engine.asset_pipeline import AnimationAssetPipeline
from applications.content_factory.animation_engine.renderer import AnimationRenderer
from applications.content_factory.animation_engine.quality import AnimationQualityEvaluator
from applications.content_factory.animation_engine.validator import AnimationValidator
from applications.content_factory.animation_engine.telemetry import AnimationEngineTelemetry


@pytest.fixture
def animation_stack(tmp_path):
    storage = ProjectStorage(root_dir=str(tmp_path))
    asset_manager = AssetManager(storage)
    
    project_manager = ProjectManager(storage, MagicMock(), asset_manager, MagicMock(), MagicMock())
    
    # Initialize the project bundle directory structure using the storage manager
    project_dir = storage.get_absolute_path("test_proj", "")
    os.makedirs(project_dir, exist_ok=True)
    
    renderer = AnimationRenderer()
    evaluator = AnimationQualityEvaluator()
    validator = AnimationValidator()
    pipeline = AnimationAssetPipeline(project_manager)
    scheduler = AnimationScheduler(max_workers=2)
    telemetry = AnimationEngineTelemetry(MagicMock())
    
    planner = AnimationGenerationPlanner(
        renderer, evaluator, validator, pipeline, scheduler, telemetry, max_retries=1
    )
    manager = AnimationEngineManager(planner, MagicMock(), project_manager)
    return manager, planner, pipeline, project_dir


def test_animation_batch_generation(animation_stack):
    manager, planner, pipeline, project_dir = animation_stack
    
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
            visual_style_override="Anime",
            scenes=[
                StoryboardScene(
                    scene_number=1, narration="", dialogue="", duration=2.0, camera_angle="", camera_movement="pan right",
                    composition="", shot_type="", lighting="", time_of_day="", environment="", location="",
                    characters="", character_positions="", character_expressions="", character_motion="running very fast", props="",
                    background="", foreground="", color_palette="", mood="", visual_style="", animation_notes="",
                    transition="", sound_effects="", music_cue="", voice_timing="", image_prompt="Run",
                    negative_prompt="", comfyui_prompt="", flux_prompt="", wan_prompt="", thumbnail_candidate=False
                )
            ]
        )
    )
    
    # Execute
    updated_bundle = planner.execute_batch(bundle, "wan")
    
    # Verify clip was saved
    scene_dir = os.path.join(project_dir, "animations", "scene_001")
    assert os.path.exists(scene_dir)
    assert os.path.exists(os.path.join(scene_dir, "clip_v1.mp4"))
    assert os.path.exists(os.path.join(scene_dir, "metadata.json"))

def test_adapter_failure_and_retries(animation_stack):
    manager, planner, pipeline, project_dir = animation_stack
    
    # Mock renderer to fail first time, succeed second
    call_count = [0]
    def mock_render(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise ValueError("Adapter error")
        return b"MOCK_VIDEO"
        
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
            visual_style_override="Anime",
            scenes=[
                StoryboardScene(
                    scene_number=1, narration="", dialogue="", duration=2.0, camera_angle="", camera_movement="pan right",
                    composition="", shot_type="", lighting="", time_of_day="", environment="", location="",
                    characters="", character_positions="", character_expressions="", character_motion="running very fast", props="",
                    background="", foreground="", color_palette="", mood="", visual_style="", animation_notes="",
                    transition="", sound_effects="", music_cue="", voice_timing="", image_prompt="Run",
                    negative_prompt="", comfyui_prompt="", flux_prompt="", wan_prompt="", thumbnail_candidate=False
                )
            ]
        )
    )
    
    updated_bundle = planner.execute_batch(bundle, "wan")
    assert call_count[0] == 2
    
    scene_dir = os.path.join(project_dir, "animations", "scene_001")
    assert os.path.exists(os.path.join(scene_dir, "clip_v1.mp4"))
