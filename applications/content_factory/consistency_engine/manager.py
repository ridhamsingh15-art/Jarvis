"""
Capability Facade for the Consistency Engine.
"""

import logging
from typing import List

from applications.content_factory.storyboard_engine.models import StoryboardScene
from core.capability.models import Capability, CapabilityType

from .asset_matcher import AssetMatcher
from .prompt_enricher import PromptEnricher
from .character_library import CharacterLibrary
from .environment_library import EnvironmentLibrary
from .object_library import ObjectLibrary
from .telemetry import ConsistencyTelemetry
from .models import EnrichmentResult

logger = logging.getLogger(__name__)


class ConsistencyEngineManager:
    """Public facade for Character & Asset Consistency."""

    def __init__(
        self,
        character_library: CharacterLibrary,
        environment_library: EnvironmentLibrary,
        object_library: ObjectLibrary,
        matcher: AssetMatcher,
        enricher: PromptEnricher,
        telemetry: ConsistencyTelemetry
    ) -> None:
        self.characters = character_library
        self.environments = environment_library
        self.objects = object_library
        self._matcher = matcher
        self._enricher = enricher
        self._telemetry = telemetry

    def get_capability_metadata(self) -> Capability:
        return Capability(
            name="consistency_engine",
            description="Maintains visual consistency across an entire project by providing reference assets during image generation.",
            type=CapabilityType.AGENT
        )

    def enrich_scene(self, project_id: str, scene: StoryboardScene) -> EnrichmentResult:
        """
        Analyzes a storyboard scene, matches consistency profiles, 
        and returns an enriched prompt.
        """
        matched_chars, matched_envs, matched_objs = self._matcher.match_scene(project_id, scene)
        
        enriched_prompt = self._enricher.enrich(
            scene.image_prompt,
            matched_chars,
            matched_envs,
            matched_objs
        )
        
        # We emit telemetry so it tracks for Mission Control
        self._telemetry.emit_enrichment_completed(
            project_id=project_id,
            scene_number=scene.scene_number,
            matched_chars=[c.name for c in matched_chars],
            matched_envs=[e.name for e in matched_envs],
            matched_objs=[o.name for o in matched_objs]
        )
        
        return EnrichmentResult(
            original_prompt=scene.image_prompt,
            enriched_prompt=enriched_prompt,
            matched_characters=[c.name for c in matched_chars],
            matched_environments=[e.name for e in matched_envs],
            matched_objects=[o.name for o in matched_objs]
        )
