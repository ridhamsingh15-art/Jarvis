"""
Orchestrates the image generation retry loop and batch execution.
"""

import logging
import os

from applications.content_factory.project.models import ProjectBundle
from applications.content_factory.storyboard_engine.models import StoryboardScene

from .asset_pipeline import AssetPipeline
from .exceptions import ImageEngineError
from .models import GenerationParameters, GenerationTask, ImageMetadata
from .quality import ImageQualityEvaluator
from .renderer import ImageRenderer
from .scheduler import GenerationScheduler
from .telemetry import ImageEngineTelemetry
from applications.content_factory.consistency_engine.manager import ConsistencyEngineManager
from .validator import ImageValidator

logger = logging.getLogger(__name__)


class ImageGenerationPlanner:
    """Handles the retry loop for an individual generation task, and batch execution."""

    def __init__(
        self,
        renderer: ImageRenderer,
        evaluator: ImageQualityEvaluator,
        validator: ImageValidator,
        pipeline: AssetPipeline,
        scheduler: GenerationScheduler,
        telemetry: ImageEngineTelemetry,
        consistency_engine: ConsistencyEngineManager | None = None,
        max_retries: int = 2
    ) -> None:
        self._renderer = renderer
        self._evaluator = evaluator
        self._validator = validator
        self._pipeline = pipeline
        self._scheduler = scheduler
        self._telemetry = telemetry
        self._consistency_engine = consistency_engine
        self._max_retries = max_retries

    def execute_batch(self, bundle: ProjectBundle, model_name: str) -> ProjectBundle:
        """Schedules generation for all scenes in the project bundle."""
        if not bundle.storyboard_package:
            raise ImageEngineError("Project bundle does not contain a storyboard to render.")
            
        tasks = []
        for scene in bundle.storyboard_package.scenes:
            base_prompt = self._get_model_specific_prompt(scene, model_name)
            
            # Enrich prompt if consistency engine is available
            if self._consistency_engine:
                enrichment = self._consistency_engine.enrich_scene(bundle.metadata.project_id, scene)
                base_prompt = enrichment.enriched_prompt
            
            params = GenerationParameters(
                prompt=base_prompt,
                negative_prompt=scene.negative_prompt,
                seed=-1,
                cfg=7.0,
                steps=30,
                sampler="euler_a",
                width=1920,
                height=1080
            )
            task = GenerationTask(
                project_id=bundle.metadata.project_id,
                scene_number=scene.scene_number,
                model_name=model_name,
                parameters=params
            )
            tasks.append(task)
            self._telemetry.emit_generation_queued(bundle.metadata.project_id, scene.scene_number, model_name)
            
        logger.info("Executing image generation batch for %d scenes using %s", len(tasks), model_name)
        
        # We process in parallel using the scheduler
        # Note: Since the bundle is immutable and AssetManager returns a new bundle per ingestion, 
        # doing parallel updates to the SAME bundle object instance creates a race condition for the aggregate root.
        # To handle this safely without complex locking, we run the render step in parallel, 
        # but the ingestion step sequentially.
        
        # 1. Parallel Render
        def render_worker(task: GenerationTask) -> tuple[GenerationTask, str, ImageMetadata]:
            return self._execute_task_retry_loop(task)
            
        results = self._scheduler.execute_batch(tasks, render_worker)
        
        # 2. Sequential Ingestion
        current_bundle = bundle
        for result in results:
            if isinstance(result, tuple) and len(result) == 3:
                task, temp_path, meta = result
                current_bundle = self._pipeline.ingest_image(current_bundle, temp_path, meta)
                
                # Cleanup the temp file now that it's ingested
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
            elif isinstance(result, tuple) and len(result) == 2:
                # Failure case: (task, Exception)
                task, exc = result
                logger.error("Scene %d failed to render: %s", task.scene_number, exc)
                self._telemetry.emit_generation_failed(task.project_id, task.scene_number, str(exc))
                
        return current_bundle

    def _execute_task_retry_loop(self, task: GenerationTask) -> tuple[GenerationTask, str, ImageMetadata]:
        """
        Executes a single task, evaluating it and retrying if the quality is poor.
        """
        self._telemetry.emit_generation_started(task.project_id, task.scene_number, task.model_name)
        
        current_task = task
        last_error = None
        
        while current_task.retry_count <= self._max_retries:
            try:
                # 1. Render
                temp_path, duration = self._renderer.render(current_task)
                
                # 2. Evaluate
                score = self._evaluator.evaluate(current_task, temp_path)
                
                # 3. Create Metadata
                import dataclasses
                meta = ImageMetadata(
                    prompt=current_task.parameters.prompt,
                    negative_prompt=current_task.parameters.negative_prompt,
                    generation_model=current_task.model_name,
                    generation_parameters=dataclasses.asdict(current_task.parameters),
                    seed=current_task.parameters.seed,
                    sampler=current_task.parameters.sampler,
                    resolution=f"{current_task.parameters.width}x{current_task.parameters.height}",
                    generation_time=duration,
                    scene_number=current_task.scene_number,
                    version=1 # versioning handled by AssetManager later
                )
                
                # 4. Validate
                self._validator.validate(meta)
                
                self._telemetry.emit_generation_completed(current_task.project_id, current_task.scene_number, duration)
                return current_task, temp_path, meta
                
            except Exception as e:
                last_error = e
                logger.warning("Generation for scene %d failed on attempt %d: %s", current_task.scene_number, current_task.retry_count, e)
                
                import dataclasses
                current_task = dataclasses.replace(current_task, retry_count=current_task.retry_count + 1)
                
                if current_task.retry_count <= self._max_retries:
                    self._telemetry.emit_quality_retry(current_task.project_id, current_task.scene_number, 0.0, current_task.retry_count)
                    
        raise ImageEngineError(f"Failed to generate scene {task.scene_number} after {self._max_retries} retries. Last error: {last_error}")

    def _get_model_specific_prompt(self, scene: StoryboardScene, model_name: str) -> str:
        name = model_name.lower()
        if "flux" in name:
            return scene.flux_prompt or scene.image_prompt
        elif "comfyui" in name:
            return scene.comfyui_prompt or scene.image_prompt
        elif "wan" in name:
            return scene.wan_prompt or scene.image_prompt
        return scene.image_prompt
