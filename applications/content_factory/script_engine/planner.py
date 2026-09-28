"""
Orchestrates the multi-stage script generation pipeline.
"""

import logging
import time

from .exceptions import ScriptEngineError
from .formatter import format_script
from .generator import ScriptGenerator
from .models import ScriptPackage
from .quality import evaluate_quality
from .telemetry import ScriptEngineTelemetry
from .validator import validate_script

logger = logging.getLogger(__name__)


class ScriptPlanner:
    """State machine for executing the script production plan."""

    def __init__(
        self,
        generator: ScriptGenerator,
        telemetry: ScriptEngineTelemetry
    ) -> None:
        self._generator = generator
        self._telemetry = telemetry

    def execute_plan(
        self, 
        mission_id: str, 
        topic: str, 
        style: str, 
        context: str = ""
    ) -> ScriptPackage:
        """Executes the pipeline: Generate -> Format -> Validate -> Quality Review."""
        logger.info("Starting Script Generation Plan for topic: %s", topic)
        self._telemetry.emit_script_started(topic, mission_id)
        start_time = time.time()

        try:
            # 1. Generate & Format (Research -> Outline -> Scene Structure -> Script -> Prompt Gen)
            # The LLM does this in a single massive chain of thought based on the prompt.
            logger.debug("Generating raw JSON payload...")
            raw_data = self._generator.generate_raw_script(topic, style, context)
            
            logger.debug("Formatting into ScriptPackage model...")
            package = format_script(raw_data)

            # 2. Validation
            logger.debug("Validating script integrity...")
            try:
                validate_script(package)
            except Exception as e:
                self._telemetry.emit_validation_failed(mission_id, [str(e)])
                raise

            # 3. Quality Review
            logger.debug("Evaluating script quality...")
            score = evaluate_quality(package)
            logger.info("Script quality score: %.2f/100", score)

            # Done
            duration = time.time() - start_time
            self._telemetry.emit_script_finished(package.title, mission_id, duration)
            return package
            
        except Exception as e:
            logger.error("Script production plan failed: %s", e)
            self._telemetry.emit_script_failed(mission_id, str(e))
            raise ScriptEngineError(f"Script production failed: {e}") from e
