"""
Quality Evaluator for Animation Engine.
"""

from .exceptions import AnimationQualityError
from .models import AnimationParameters


class AnimationQualityEvaluator:
    """
    Evaluates generated animation heuristics (mocked for this iteration).
    In a real system, this might call a Vision-Language Model to assess motion smoothness.
    """

    def evaluate(self, animation_data: bytes, params: AnimationParameters) -> float:
        """
        Returns a quality score between 0.0 and 1.0.
        Throws AnimationQualityError if the animation is completely corrupted.
        """
        if not animation_data:
            raise AnimationQualityError("Generated animation data is completely empty.")

        # Simulate heuristic checking based on prompt length and motion type
        score = 0.95
        
        if "fast" in params.camera_motion.lower():
            score -= 0.1  # Fast motion can be blurry
            
        if len(params.motion_prompt) < 10:
            score -= 0.2  # Too short prompt might lack detail
            
        return max(0.0, min(1.0, score))
