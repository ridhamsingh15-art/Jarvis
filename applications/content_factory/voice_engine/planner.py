"""
Planner for the Voice Engine.
"""

import logging
import uuid
import os
import datetime
from typing import List

from applications.content_factory.project.models import ProjectBundle
from applications.content_factory.storyboard_engine.models import StoryboardScene

from .renderer import VoiceRenderer
from .quality import VoiceQualityEvaluator
from .validator import VoiceValidator
from .asset_pipeline import VoiceAssetPipeline
from .scheduler import VoiceScheduler
from .telemetry import VoiceEngineTelemetry
from .models import VoiceParameters, VoiceTask, VoiceMetadata
from .exceptions import VoiceEngineError

logger = logging.getLogger(__name__)


class VoiceGenerationPlanner:
    """Orchestrates generation, quality evaluation, and retries for a batch of voices."""

    def __init__(
        self,
        renderer: VoiceRenderer,
        evaluator: VoiceQualityEvaluator,
        validator: VoiceValidator,
        pipeline: VoiceAssetPipeline,
        scheduler: VoiceScheduler,
        telemetry: VoiceEngineTelemetry,
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
        """Plans and executes voice generation for all scenes in the bundle."""
        if not bundle.storyboard_package:
            raise VoiceEngineError("No storyboard package found in bundle.")
            
        tasks = []
        for scene in bundle.storyboard_package.scenes:
            # We combine narration and dialogue if both are present, or pick one.
            # Usually narration and dialogue might require different voices, but for simplicity
            # in this generation, we use one audio file per scene.
            text = (scene.narration + " " + scene.dialogue).strip()
            if not text:
                continue  # Skip scenes without voiceover text
                
            is_narration = bool(scene.narration)
            speaker = "narrator" if is_narration else "character_1"

            params = VoiceParameters(
                text=text,
                speaker=speaker,
                language="en",
                speed=1.0,
                emotion=scene.mood or "neutral",
                is_narration=is_narration
            )
            
            task = VoiceTask(
                task_id=str(uuid.uuid4()),
                scene_number=scene.scene_number,
                model_name=model_name,
                parameters=params
            )
            tasks.append(task)
            
        if not tasks:
            return bundle # Nothing to generate
            
        def render_worker(t: VoiceTask) -> tuple[VoiceTask, str, VoiceMetadata]:
            return self._generate_with_retries(bundle, t)
            
        results = self._scheduler.execute_batch(tasks, render_worker)
        
        current_bundle = bundle
        for task_id, result in results.items():
            if isinstance(result, tuple) and len(result) == 3:
                task, temp_path, meta = result
                current_bundle = self._pipeline.ingest_voice(current_bundle, temp_path, meta)
                
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
            elif isinstance(result, tuple) and len(result) == 2:
                # Failed task
                task, error = result
                logger.error("Failed to generate voice for scene %s: %s", task.scene_number, error)
                        
        return current_bundle

    def _generate_with_retries(self, bundle: ProjectBundle, task: VoiceTask) -> tuple[VoiceTask, str, VoiceMetadata]:
        """Executes a single voice task with built-in retry logic."""
        start_time = self._telemetry.emit_generation_started(
            bundle.metadata.project_id, task.scene_number, task.model_name, task.parameters.speaker
        )
        
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                # 1. Render
                audio_data = self._renderer.render(task.model_name, task.parameters)
                
                # Write to temp file
                import tempfile
                fd, temp_path = tempfile.mkstemp(suffix=".wav")
                os.write(fd, audio_data)
                os.close(fd)
                
                # 2. Evaluate
                score, duration = self._evaluator.evaluate(audio_data, task.parameters)
                if score < self._min_quality_score:
                    raise VoiceEngineError(f"Quality score {score} is below threshold {self._min_quality_score}.")
                    
                # 3. Create Metadata
                meta = VoiceMetadata(
                    scene_number=task.scene_number,
                    duration_seconds=duration,
                    model_name=task.model_name,
                    speaker=task.parameters.speaker,
                    language=task.parameters.language,
                    speed=task.parameters.speed,
                    emotion=task.parameters.emotion,
                    text=task.parameters.text,
                    voice_id=task.parameters.voice_id,
                    is_narration=task.parameters.is_narration,
                    generation_parameters={
                        "language": task.parameters.language,
                        "speed": task.parameters.speed,
                        "emotion": task.parameters.emotion,
                        "voice_id": task.parameters.voice_id
                    },
                    version=1,
                    timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
                )
                
                self._validator.validate_metadata(meta)
                
                self._telemetry.emit_generation_completed(
                    bundle.metadata.project_id, task.scene_number, task.model_name, task.parameters.speaker, start_time, score, attempt
                )
                return task, temp_path, meta
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Voice attempt {attempt + 1}/{self._max_retries + 1} failed for scene {task.scene_number}: {e}"
                )
                
        self._telemetry.emit_generation_failed(
            bundle.metadata.project_id, task.scene_number, task.model_name, task.parameters.speaker, str(last_error)
        )
        raise VoiceEngineError(f"Failed to generate voice after {self._max_retries} retries: {last_error}")
