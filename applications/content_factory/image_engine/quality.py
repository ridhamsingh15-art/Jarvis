"""
Evaluates the quality of a generated image heuristically.
"""

from pathlib import Path

from .exceptions import ImageQualityError
from .models import GenerationTask


class ImageQualityEvaluator:
    """Evaluates the physical image and prompt adherence."""

    def evaluate(self, task: GenerationTask, image_path: str) -> float:
        """
        Evaluates the generated image.
        In a real implementation, this might run a lightweight VQA or CLIP model to check prompt adherence
        and calculate blur/noise metrics using OpenCV.
        
        For now, this is a simulated heuristic.
        """
        score = 100.0
        
        path = Path(image_path)
        if not path.exists():
            raise ImageQualityError(f"Image file does not exist at {image_path}")
            
        if path.stat().st_size < 10:
            score -= 50  # File is suspiciously small (likely corrupt or empty)
            
        # Mock logic based on task parameters
        if "bad" in task.parameters.prompt.lower():
            score -= 40
            
        if score < 70.0:
            raise ImageQualityError(f"Image quality score {score}/100 falls below threshold.")
            
        return score
