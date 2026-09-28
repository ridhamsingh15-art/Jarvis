"""
Tests for the AI Content Factory: Consistency Engine.
"""

from unittest.mock import MagicMock

from applications.content_factory.consistency_engine.asset_matcher import AssetMatcher
from applications.content_factory.consistency_engine.character_library import CharacterLibrary
from applications.content_factory.consistency_engine.environment_library import EnvironmentLibrary
from applications.content_factory.consistency_engine.exceptions import ConsistencyValidationError
from applications.content_factory.consistency_engine.manager import ConsistencyEngineManager
from applications.content_factory.consistency_engine.models import CharacterProfile, EnvironmentProfile
from applications.content_factory.consistency_engine.object_library import ObjectLibrary
from applications.content_factory.consistency_engine.prompt_enricher import PromptEnricher
from applications.content_factory.consistency_engine.registry import ConsistencyRegistry
from applications.content_factory.consistency_engine.telemetry import ConsistencyTelemetry
from applications.content_factory.consistency_engine.validator import ProfileValidator
from applications.content_factory.storyboard_engine.models import StoryboardScene

import pytest


@pytest.fixture
def consistency_stack():
    registry = ConsistencyRegistry()
    validator = ProfileValidator()
    telemetry = ConsistencyTelemetry(MagicMock())
    
    char_lib = CharacterLibrary(registry, validator, telemetry)
    env_lib = EnvironmentLibrary(registry, validator, telemetry)
    obj_lib = ObjectLibrary(registry, validator, telemetry)
    
    matcher = AssetMatcher(registry)
    enricher = PromptEnricher()
    
    manager = ConsistencyEngineManager(char_lib, env_lib, obj_lib, matcher, enricher, telemetry)
    return manager


def test_character_validation(consistency_stack):
    with pytest.raises(ConsistencyValidationError):
        consistency_stack.characters.create_character("p1", name="", description="No name character")


def test_asset_matching_and_enrichment(consistency_stack):
    # 1. Register profiles
    consistency_stack.characters.create_character(
        "p1", 
        name="Ram", 
        description="A noble prince", 
        clothing="saffron dhoti", 
        face_reference="calm, serene expression"
    )
    
    consistency_stack.environments.create_environment(
        "p1", 
        name="Ayodhya", 
        description="A grand ancient city", 
        architecture_style="Vedic, grand palaces"
    )
    
    consistency_stack.objects.create_object(
        "p1",
        name="Bow",
        description="A divine wooden bow",
        material="divine wood, gold accents"
    )
    
    # 2. Create a scene prompt
    scene = StoryboardScene(
        scene_number=1, narration="", dialogue="", duration=1.0, camera_angle="", camera_movement="",
        composition="", shot_type="", lighting="", time_of_day="", environment="", location="",
        characters="", character_positions="", character_expressions="", character_motion="", props="",
        background="", foreground="", color_palette="", mood="", visual_style="", animation_notes="",
        transition="", sound_effects="", music_cue="", voice_timing="", image_prompt="Ram stands in Ayodhya holding his Bow.",
        negative_prompt="", comfyui_prompt="", flux_prompt="", wan_prompt="", thumbnail_candidate=False
    )
    
    # 3. Enrich
    result = consistency_stack.enrich_scene("p1", scene)
    
    # 4. Verify Matches
    assert "Ram" in result.matched_characters
    assert "Ayodhya" in result.matched_environments
    assert "Bow" in result.matched_objects
    
    # 5. Verify Enrichment String
    assert "CONSISTENCY REFERENCES" in result.enriched_prompt
    assert "saffron dhoti" in result.enriched_prompt
    assert "Vedic, grand palaces" in result.enriched_prompt
    assert "divine wood, gold accents" in result.enriched_prompt
