"""
Tests for the AI Content Factory: Image Generation Engine.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from applications.content_factory.image_engine.asset_pipeline import AssetPipeline
from applications.content_factory.image_engine.exceptions import (
    ImageQualityError,
)
from applications.content_factory.image_engine.manager import ImageEngineManager
from applications.content_factory.image_engine.models import (
    GenerationParameters,
    GenerationTask,
)
from applications.content_factory.image_engine.planner import ImageGenerationPlanner
from applications.content_factory.image_engine.quality import ImageQualityEvaluator
from applications.content_factory.image_engine.renderer import ImageRenderer
from applications.content_factory.image_engine.scheduler import GenerationScheduler
from applications.content_factory.image_engine.telemetry import ImageEngineTelemetry
from applications.content_factory.image_engine.validator import (
    ImageValidator as ImageEngineValidator,
)
from applications.content_factory.project.asset_manager import AssetManager
from applications.content_factory.project.manager import ProjectManager
from applications.content_factory.project.registry import ProjectRegistry
from applications.content_factory.project.storage import ProjectStorage
from applications.content_factory.project.telemetry import ProjectManagerTelemetry
from applications.content_factory.project.validator import ProjectValidator
from applications.content_factory.storyboard_engine.models import (
    StoryboardPackage,
    StoryboardScene,
)


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def image_engine_stack(temp_workspace):
    # Setup Project Manager
    storage = ProjectStorage(root_dir=str(Path(temp_workspace) / "projects"))
    registry = ProjectRegistry(storage)
    asset_manager = AssetManager(storage)
    pm_validator = ProjectValidator(storage)
    pm_telemetry = ProjectManagerTelemetry(MagicMock())
    project_manager = ProjectManager(storage, registry, asset_manager, pm_validator, pm_telemetry)

    # Setup Image Engine
    renderer = ImageRenderer()
    evaluator = ImageQualityEvaluator()
    validator = ImageEngineValidator()
    pipeline = AssetPipeline(project_manager)
    scheduler = GenerationScheduler(max_workers=2)
    telemetry = ImageEngineTelemetry(MagicMock())
    
    planner = ImageGenerationPlanner(
        renderer, evaluator, validator, pipeline, scheduler, telemetry, max_retries=1
    )
    manager = ImageEngineManager(planner, MagicMock(), project_manager)
    
    return project_manager, planner, renderer, evaluator, storage


def test_renderer_output(image_engine_stack):
    _, _, renderer, _, _ = image_engine_stack
    
    task = GenerationTask(
        project_id="p123",
        scene_number=1,
        model_name="flux",
        parameters=GenerationParameters(prompt="A futuristic city")
    )
    
    path, duration = renderer.render(task)
    assert os.path.exists(path)
    assert duration > 0
    os.remove(path)


def test_quality_evaluator_failure(image_engine_stack):
    _, _, renderer, evaluator, _ = image_engine_stack
    
    task = GenerationTask(
        project_id="p123",
        scene_number=1,
        model_name="flux",
        parameters=GenerationParameters(prompt="A very bad small corrupt rendering")
    )
    
    path, _ = renderer.render(task)
    
    with pytest.raises(ImageQualityError):
        evaluator.evaluate(task, path)
        
    os.remove(path)


def test_full_pipeline_ingestion(image_engine_stack):
    project_manager, planner, _, _, storage = image_engine_stack
    
    # 1. Create a project bundle with a mock storyboard
    bundle = project_manager.create_project(title="Test Pipeline")
    
    def make_dummy_scene(num: int, prompt: str) -> StoryboardScene:
        return StoryboardScene(
            scene_number=num, narration="", dialogue="", duration=1.0, camera_angle="", camera_movement="",
            composition="", shot_type="", lighting="", time_of_day="", environment="", location="",
            characters="", character_positions="", character_expressions="", character_motion="", props="",
            background="", foreground="", color_palette="", mood="", visual_style="", animation_notes="",
            transition="", sound_effects="", music_cue="", voice_timing="", image_prompt=prompt,
            negative_prompt="", comfyui_prompt="", flux_prompt="", wan_prompt="", thumbnail_candidate=False
        )

    scenes = [
        make_dummy_scene(1, "Hero looking at horizon"),
        make_dummy_scene(2, "Villain laughing")
    ]
    sb_package = StoryboardPackage(script_title="Test Pipeline", scenes=scenes, visual_style_override="Cinematic")
    
    from applications.content_factory.project.bundle import BundleModifier
    bundle = BundleModifier.set_storyboard(bundle, sb_package)
    project_manager.save_project(bundle)
    
    # 2. Execute Image Generation Batch
    updated_bundle = planner.execute_batch(bundle, model_name="flux")
    
    # 3. Assertions
    assert len(updated_bundle.assets) == 2
    
    # Sort assets by scene_number to avoid ThreadPoolExecutor ordering flakiness
    assets = sorted(updated_bundle.assets, key=lambda a: a.scene_number)
    
    asset_1 = assets[0]
    asset_2 = assets[1]
    
    assert asset_1.scene_number == 1
    assert asset_1.metadata.version == 1
    assert asset_1.relative_path == "images/scene_001/image_v1.png"
    
    assert asset_2.scene_number == 2
    assert asset_2.metadata.version == 1
    assert asset_2.relative_path == "images/scene_002/image_v1.png"
    
    # Verify disk
    proj_dir = storage.root_dir / bundle.metadata.project_id
    assert (proj_dir / "images" / "scene_001" / "image_v1.png").exists()
    assert (proj_dir / "images" / "scene_001" / "metadata.json").exists()
    assert (proj_dir / "images" / "scene_002" / "image_v1.png").exists()
    assert (proj_dir / "images" / "scene_002" / "metadata.json").exists()
