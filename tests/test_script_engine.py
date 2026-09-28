"""
Tests for the AI Content Factory: Script Generation Engine.
"""

import json
from unittest.mock import MagicMock

import pytest

from applications.content_factory.script_engine.exceptions import (
    ScriptQualityError,
    ScriptValidationError,
)
from applications.content_factory.script_engine.formatter import format_script
from applications.content_factory.script_engine.generator import ScriptGenerator
from applications.content_factory.script_engine.manager import ScriptEngineManager
from applications.content_factory.script_engine.quality import evaluate_quality
from applications.content_factory.script_engine.validator import validate_script
from core.mission.models import Mission
from core.models import Metadata
from providers.provider_models import ModelResponse


@pytest.fixture
def sample_raw_script():
    return {
        "title": "Epic Ramayana Story",
        "summary": "A grand tale of duty.",
        "target_audience": "General",
        "estimated_duration": "5 minutes",
        "voice_style": "Epic and serious",
        "music_suggestion": "Orchestral, traditional",
        "seo": {
            "thumbnail_idea": "Rama with bow",
            "keywords": ["ramayana", "epic"],
            "description_draft": "Watch the epic tale.",
            "tags": ["history", "mythology", "india"]
        },
        "scenes": [
            {
                "scene_number": 1,
                "narration": "In the kingdom of Ayodhya... " * 10,
                "visual_description": "A sweeping shot of a golden city. " * 5,
                "image_prompt": "Golden ancient Indian city, cinematic lighting",
                "animation_prompt": "Slow pan left",
                "sound_effects": "City ambiance",
                "transition_notes": "Cut to palace"
            },
            {
                "scene_number": 2,
                "narration": "King Dasharatha ruled with wisdom... " * 10,
                "visual_description": "The old king sitting on his throne. " * 5,
                "image_prompt": "Old Indian king, ornate throne",
                "animation_prompt": "Zoom in slowly",
                "sound_effects": "Royal trumpets",
                "transition_notes": "Fade out"
            }
        ]
    }


def test_formatter(sample_raw_script):
    package = format_script(sample_raw_script)
    assert package.title == "Epic Ramayana Story"
    assert len(package.scenes) == 2
    assert package.seo.keywords == ["ramayana", "epic"]
    assert package.scenes[0].scene_number == 1


def test_validator_success(sample_raw_script):
    package = format_script(sample_raw_script)
    # Should not raise
    validate_script(package)


def test_validator_missing_narration(sample_raw_script):
    sample_raw_script["scenes"][0]["narration"] = "   "
    package = format_script(sample_raw_script)
    
    with pytest.raises(ScriptValidationError, match="contains empty narration"):
        validate_script(package)


def test_validator_scene_order(sample_raw_script):
    sample_raw_script["scenes"][1]["scene_number"] = 3
    package = format_script(sample_raw_script)
    
    with pytest.raises(ScriptValidationError, match="Scene numbers out of order"):
        validate_script(package)


def test_quality_evaluation(sample_raw_script):
    package = format_script(sample_raw_script)
    score = evaluate_quality(package)
    assert score >= 70.0


def test_quality_evaluation_failure(sample_raw_script):
    # Make narration too short
    sample_raw_script["scenes"][0]["narration"] = "Too short."
    sample_raw_script["scenes"][1]["narration"] = "Also short."
    package = format_script(sample_raw_script)
    
    with pytest.raises(ScriptQualityError):
        evaluate_quality(package)


def test_generator(sample_raw_script):
    mock_router = MagicMock()
    # Mock LLM returning our sample JSON
    mock_router.generate.return_value = ModelResponse(
        text=json.dumps(sample_raw_script),
        provider_id="test",
        model_id="test",
        latency_ms=100
    )
    
    generator = ScriptGenerator(mock_router)
    result = generator.generate_raw_script("Ramayana", "mythology")
    
    assert result["title"] == "Epic Ramayana Story"
    
    
def test_manager_async_flow(sample_raw_script):
    mock_planner = MagicMock()
    # Return a real dataclass instead of a MagicMock so dataclasses.asdict works
    mock_planner.execute_plan.return_value = format_script(sample_raw_script)
    
    mock_mission_manager = MagicMock()
    
    mission = Mission(
        title="Write Script: test...",
        description="Generating a test script about test.",
        priority=2,
        metadata=Metadata(annotations={"topic": "test", "style": "test", "context": ""})
    )
    
    mock_mission_manager.create.return_value = mission
    mock_mission_manager.get.return_value = mission
    
    manager = ScriptEngineManager(mock_planner, mock_mission_manager)
    mission_id = manager.generate_script_async("test", "test", "")
    
    assert mission_id == mission.mission_id.value
    
    mock_mission_manager.reset_mock()
    mock_planner.reset_mock()
    
    # Manually run the thread function
    manager._run_and_monitor(mission_id, "test", "test", "")
    
    mock_mission_manager.ready.assert_called_once()
    mock_mission_manager.complete.assert_called_once()
    mock_planner.execute_plan.assert_called_once()
