"""
Orchestrates the multi-stage storyboard generation pipeline.
"""

import logging
import time

from applications.content_factory.script_engine.models import ScriptPackage

from .exceptions import StoryboardEngineError
from .formatter import format_storyboard
from .generator import StoryboardGenerator
from .models import StoryboardPackage
from .prompts import PromptAdapterRegistry
from .quality import evaluate_quality
from .telemetry import StoryboardEngineTelemetry
from .validator import validate_storyboard

logger = logging.getLogger(__name__)


class StoryboardPlanner:
    """State machine for executing the storyboard production plan."""

    def __init__(
        self,
        generator: StoryboardGenerator,
        telemetry: StoryboardEngineTelemetry
    ) -> None:
        self._generator = generator
        self._telemetry = telemetry

    def execute_plan(
        self, 
        mission_id: str, 
        script: ScriptPackage, 
        visual_style: str = ""
    ) -> StoryboardPackage:
        """Executes the pipeline: Generate -> Format -> Inject Adapters -> Validate -> Quality Review."""
        logger.info("Starting Storyboard Generation Plan for script: %s", script.title)
        self._telemetry.emit_storyboard_started(script.title, mission_id)
        start_time = time.time()

        try:
            # 1. Generate & Format
            logger.debug("Generating raw storyboard JSON payload...")
            raw_data = self._generator.generate_raw_storyboard(script, visual_style)
            
            # The raw data doesn't have the model-specific prompts yet (comfyui, flux, wan)
            # The formatter maps what it can. 
            logger.debug("Formatting into StoryboardPackage model...")
            package = format_storyboard(raw_data)

            # 2. Inject Prompt Adapters
            logger.debug("Applying model-specific prompt adapters...")
            package = self._apply_adapters(package)

            # 3. Validation
            logger.debug("Validating storyboard integrity...")
            try:
                validate_storyboard(package)
            except Exception as e:
                self._telemetry.emit_validation_failed(mission_id, [str(e)])
                raise

            # 4. Quality Review
            logger.debug("Evaluating storyboard quality...")
            score = evaluate_quality(package)
            logger.info("Storyboard quality score: %.2f/100", score)

            # Done
            duration = time.time() - start_time
            self._telemetry.emit_storyboard_finished(package.script_title, mission_id, duration, len(package.scenes))
            return package
            
        except Exception as e:
            logger.error("Storyboard production plan failed: %s", e)
            self._telemetry.emit_storyboard_failed(mission_id, str(e))
            raise StoryboardEngineError(f"Storyboard production failed: {e}") from e

    def _apply_adapters(self, package: StoryboardPackage) -> StoryboardPackage:
        """Hydrates the storyboard scenes with model-specific prompts."""
        flux = PromptAdapterRegistry.get("flux")
        sdxl = PromptAdapterRegistry.get("sdxl")
        comfyui = PromptAdapterRegistry.get("comfyui")
        wan = PromptAdapterRegistry.get("wan")
        
        hydrated_scenes = []
        for scene in package.scenes:
            # Reconstruct the scene with new prompts
            # dataclasses.replace is useful here
            import dataclasses
            
            flux_prompt = flux.generate_prompt(scene.image_prompt, scene.visual_style, scene.shot_type, scene.lighting, scene.negative_prompt)
            # SDXL is omitted from the model, but we could add it. We populate comfyui with it.
            comfy_prompt = comfyui.generate_prompt(scene.image_prompt, scene.visual_style, scene.shot_type, scene.lighting, scene.negative_prompt)
            wan_prompt = wan.generate_prompt(scene.image_prompt, scene.visual_style, scene.shot_type, scene.lighting, scene.negative_prompt)
            
            hydrated = dataclasses.replace(
                scene,
                flux_prompt=flux_prompt,
                comfyui_prompt=comfy_prompt,
                wan_prompt=wan_prompt
            )
            hydrated_scenes.append(hydrated)
            
        import dataclasses
        return dataclasses.replace(package, scenes=hydrated_scenes)
