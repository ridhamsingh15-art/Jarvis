"""
Tests for the AI Content Factory: Storyboard Generation Engine.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from applications.content_factory.script_engine.models import (
    ScriptPackage,
    ScriptScene,
)
from applications.content_factory.storyboard_engine.exceptions import (
    StoryboardQualityError,
    StoryboardValidationError,
)
from applications.content_factory.storyboard_engine.formatter import format_storyboard
from applications.content_factory.storyboard_engine.generator import StoryboardGenerator
from applications.content_factory.storyboard_engine.manager import (
    StoryboardEngineManager,
)
from applications.content_factory.storyboard_engine.planner import StoryboardPlanner
from applications.content_factory.storyboard_engine.quality import evaluate_quality
from applications.content_factory.storyboard_engine.validator import validate_storyboard
from core.mission.models import Mission
from core.models import Metadata
from providers.provider_models import ModelResponse


@pytest.fixture
def sample_script():
    return ScriptPackage(
        title="Epic Story",
        summary="A tale.",
        target_audience="General",
        estimated_duration="1 min",
        voice_style="Epic",
        music_suggestion="Epic music",
        scenes=[
            ScriptScene(
                scene_number=1,
                narration="In a distant land...",
                visual_description="A mountain",
                image_prompt="Mountain",
                animation_prompt="Zoom in",
                sound_effects="Wind",
                transition_notes="Cut"
            )
        ],
        seo=None
    )


@pytest.fixture
def sample_raw_storyboard():
    return {
        "scenes": [
            {
                "scene_number": 1,
                "narration": "In a distant land...",
                "dialogue": "",
                "duration": 5.0,
                "camera_angle": "Wide Shot",
                "camera_movement": "Drone push in",
                "composition": "Rule of thirds",
                "shot_type": "Establishing",
                "lighting": "Cinematic",
                "time_of_day": "Sunset",
                "environment": "Exterior",
                "location": "Mountain Peak",
                "characters": ["Hero"],
                "character_positions": "Standing on cliff",
                "character_expressions": "Determined",
                "character_motion": "Looking out",
                "props": ["Sword"],
                "background": "Sky",
                "foreground": "Rocks",
                "color_palette": ["#FF0000"],
                "mood": "Epic",
                "visual_style": "Photorealistic",
                "animation_notes": "Slow push",
                "transition": "Cut",
                "sound_effects": "Wind howling",
                "music_cue": "Drums",
                "voice_timing": "Immediate",
                "image_prompt": "A highly detailed mountain peak at sunset, hero standing with sword",
                "negative_prompt": "blurry, text, ugly",
                "thumbnail_candidate": True
            }
        ]
    }


def test_formatter(sample_raw_storyboard):
    package = format_storyboard(sample_raw_storyboard)
    assert len(package.scenes) == 1
    assert package.scenes[0].camera_angle == "Wide Shot"
    assert package.scenes[0].duration == 5.0


def test_validator_success(sample_raw_storyboard):
    package = format_storyboard(sample_raw_storyboard)
    # Should not raise
    validate_storyboard(package)


def test_validator_missing_camera(sample_raw_storyboard):
    sample_raw_storyboard["scenes"][0]["camera_angle"] = ""
    package = format_storyboard(sample_raw_storyboard)
    
    with pytest.raises(StoryboardValidationError, match="missing camera angle"):
        validate_storyboard(package)


def test_validator_missing_prompt(sample_raw_storyboard):
    sample_raw_storyboard["scenes"][0]["image_prompt"] = ""
    package = format_storyboard(sample_raw_storyboard)
    
    with pytest.raises(StoryboardValidationError, match="missing a base image prompt"):
        validate_storyboard(package)


def test_quality_evaluation(sample_raw_storyboard):
    package = format_storyboard(sample_raw_storyboard)
    score = evaluate_quality(package)
    assert score >= 70.0


def test_quality_evaluation_failure(sample_raw_storyboard):
    # Make quality terrible
    sample_raw_storyboard["scenes"][0]["image_prompt"] = "bad"
    sample_raw_storyboard["scenes"][0]["animation_notes"] = ""
    sample_raw_storyboard["scenes"][0]["camera_movement"] = ""
    sample_raw_storyboard["scenes"][0]["thumbnail_candidate"] = False
    sample_raw_storyboard["scenes"][0]["camera_angle"] = "Wide Shot"
    sample_raw_storyboard["scenes"][0]["shot_type"] = "Close up"
    sample_raw_storyboard["scenes"][0]["character_expressions"] = ""
    
    package = format_storyboard(sample_raw_storyboard)
    
    with pytest.raises(StoryboardQualityError):
        evaluate_quality(package)


def test_generator(sample_script, sample_raw_storyboard):
    mock_router = MagicMock()
    mock_router.generate.return_value = ModelResponse(
        text=json.dumps(sample_raw_storyboard),
        provider_id="test",
        model_id="test",
        latency_ms=100
    )
    
    generator = StoryboardGenerator(mock_router)
    result = generator.generate_raw_storyboard(sample_script, "Anime")
    
    assert result["scenes"][0]["camera_angle"] == "Wide Shot"
    assert result["visual_style_override"] == "Anime"
    assert result["script_title"] == "Epic Story"
    
    
def test_manager_async_flow(sample_script, sample_raw_storyboard):
    mock_planner = MagicMock()
    # Mocking a real package so dataclasses.asdict works
    package = format_storyboard(sample_raw_storyboard)
    mock_planner.execute_plan.return_value = package
    
    mock_mission_manager = MagicMock()
    
    mission = Mission(
        title="Storyboard: test",
        description="Generating.",
        priority=2,
        metadata=Metadata(annotations={})
    )
    
    mock_mission_manager.create.return_value = mission
    mock_mission_manager.get.return_value = mission
    
    with patch("threading.Thread") as mock_thread:
        manager = StoryboardEngineManager(mock_planner, mock_mission_manager)
        mission_id = manager.generate_storyboard_async(sample_script, "Anime")
        
        assert mission_id == mission.mission_id.value
        mock_thread.assert_called_once()
        
    mock_mission_manager.reset_mock()
    mock_planner.reset_mock()
    
    manager._run_and_monitor(mission_id, sample_script, "Anime")
    
    mock_mission_manager.ready.assert_called_once()
    mock_mission_manager.complete.assert_called_once()
    mock_planner.execute_plan.assert_called_once()

def test_planner_adapters(sample_script, sample_raw_storyboard):
    """Verify the planner properly hydrates the model-specific prompts."""
    generator_mock = MagicMock()
    generator_mock.generate_raw_storyboard.return_value = sample_raw_storyboard
    telemetry_mock = MagicMock()
    
    planner = StoryboardPlanner(generator_mock, telemetry_mock)
    result = planner.execute_plan("mission_id", sample_script, "Anime")
    
    scene = result.scenes[0]
    
    # Check that adapters were applied
    assert scene.flux_prompt != ""
    assert scene.comfyui_prompt != ""
    assert scene.wan_prompt != ""
    assert "Anime" in scene.comfyui_prompt or "Photorealistic" in scene.comfyui_prompt # One of the styles is injected
