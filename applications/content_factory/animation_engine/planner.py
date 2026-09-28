"""
Planner for the Animation Engine.
"""

import logging
import uuid
import os
from typing import List

from applications.content_factory.project.models import ProjectBundle
from applications.content_factory.storyboard_engine.models import StoryboardScene

from .renderer import AnimationRenderer
from .quality import AnimationQualityEvaluator
from .validator import AnimationValidator
from .asset_pipeline import AnimationAssetPipeline
from .scheduler import AnimationScheduler
from .telemetry import AnimationEngineTelemetry
from .models import AnimationParameters, AnimationTask, AnimationAsset, AnimationMetadata
from .exceptions import AnimationEngineError

logger = logging.getLogger(__name__)


class AnimationGenerationPlanner:
    """Orchestrates generation, quality evaluation, and retries for a batch of animations."""

    def __init__(
        self,
        renderer: AnimationRenderer,
        evaluator: AnimationQualityEvaluator,
        validator: AnimationValidator,
        pipeline: AnimationAssetPipeline,
        scheduler: AnimationScheduler,
        telemetry: AnimationEngineTelemetry,
        max_retries: int = 2,
        min_quality_score: float = 0.8
    ) -> None:
        self._renderer = renderer
        self._evaluator = evaluator
        self._validator = validator
        self._pipeline = pipeline
        self._scheduler = scheduler
        self._telemetry = telemetry
        self._max_retries = max_retries
        self._min_quality_score = min_quality_score

    def execute_batch(self, bundle: ProjectBundle, model_name: str) -> ProjectBundle:
        """Plans and executes animation generation for all scenes in the bundle."""
        if not bundle.storyboard_package:
            raise AnimationEngineError("No storyboard package found in bundle.")
            
        tasks = []
        for scene in bundle.storyboard_package.scenes:
            # Locate the generated image for this scene to use as base_image
            base_image_path = ""
            for asset in bundle.assets:
                if asset.metadata.asset_type == "image" and getattr(asset, "scene_number", None) == scene.scene_number:
                    # In a real system we'd get the absolute path via ProjectManager,
                    # but for this iteration and tests we'll just mock it if not accessible
                    storage = self._pipeline._project_manager._storage
                    base_image_path = storage.get_absolute_path(bundle.metadata.project_id, asset.relative_path)
                    break

            params = AnimationParameters(
                motion_prompt=scene.character_motion or scene.image_prompt,
                camera_motion=scene.camera_movement,
                negative_prompt=scene.negative_prompt,
                duration_seconds=int(scene.duration) if scene.duration > 0 else 5,
                base_image_path=base_image_path
            )
            
            task = AnimationTask(
                task_id=str(uuid.uuid4()),
                scene_number=scene.scene_number,
                model_name=model_name,
                parameters=params
            )
            tasks.append(task)
            
        def render_worker(t: AnimationTask) -> tuple[AnimationTask, str, AnimationMetadata]:
            return self._generate_with_retries(bundle, t)
            
        # Execute the batch via scheduler using our internal robust generator wrapper
        results = self._scheduler.execute_batch(
            tasks, 
            render_worker
        )
        
        current_bundle = bundle
        for result in results.values():
            if isinstance(result, tuple) and len(result) == 3:
                task, temp_path, meta = result
                current_bundle = self._pipeline.ingest_animation(current_bundle, temp_path, meta)
                
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                        
        return current_bundle

    def _generate_with_retries(self, bundle: ProjectBundle, task: AnimationTask) -> tuple[AnimationTask, str, AnimationMetadata]:
        """Executes a single animation task with built-in retry logic."""
        start_time = self._telemetry.emit_generation_started(
            bundle.metadata.project_id, task.scene_number, task.model_name
        )
        
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                # 1. Render
                animation_data = self._renderer.render(task.model_name, task.parameters)
                
                # Write to temp file
                import tempfile
                fd, temp_path = tempfile.mkstemp(suffix=".mp4")
                os.write(fd, animation_data)
                os.close(fd)
                
                # 2. Evaluate
                score = self._evaluator.evaluate(animation_data, task.parameters)
                if score < self._min_quality_score:
                    raise AnimationEngineError(f"Quality score {score} is below threshold {self._min_quality_score}.")
                    
                import datetime
                
                # 3. Create Metadata
                meta = AnimationMetadata(
                    scene_number=task.scene_number,
                    duration_seconds=task.parameters.duration_seconds,
                    fps=task.parameters.fps,
                    model_name=task.model_name,
                    motion_prompt=task.parameters.motion_prompt,
                    camera_motion=task.parameters.camera_motion,
                    generation_parameters={
                        "duration_seconds": task.parameters.duration_seconds,
                        "fps": task.parameters.fps,
                        "seed": task.parameters.seed,
                        "cfg": task.parameters.cfg,
                        "base_image_path": task.parameters.base_image_path
                    },
                    version=1,
                    timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
                )
                
                self._validator.validate_metadata(meta)
                
                self._telemetry.emit_generation_completed(
                    bundle.metadata.project_id, task.scene_number, task.model_name, start_time, score, attempt
                )
                return task, temp_path, meta
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Animation attempt {attempt + 1}/{self._max_retries + 1} failed for scene {task.scene_number}: {e}"
                )
                
        self._telemetry.emit_generation_failed(
            bundle.metadata.project_id, task.scene_number, task.model_name, str(last_error)
        )
        raise AnimationEngineError(f"Failed to generate animation after {self._max_retries} retries: {last_error}")
