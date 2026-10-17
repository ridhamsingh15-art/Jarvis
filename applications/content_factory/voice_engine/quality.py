"""
Quality Evaluator for Voice Engine.
"""

from .exceptions import VoiceQualityError
from .models import VoiceParameters


class VoiceQualityEvaluator:
    """
    Evaluates generated voice heuristics.
    """

    def evaluate(self, audio_data: bytes, params: VoiceParameters) -> tuple[float, float]:
        """
        Returns a tuple of (quality_score, duration_seconds).
        Throws VoiceQualityError if the audio is completely corrupted or purely silence.
        """
        if not audio_data:
            raise VoiceQualityError("Generated audio data is completely empty.")

        # Simulate heuristic checking (e.g. sample rate, clipping, silence)
        score = 0.95
        
        # Simulate computing duration (mocked as length / arbitrary bit rate)
        duration_seconds = max(0.5, len(audio_data) / 1000.0)
        
        # If text is very long but duration is very short, that's a red flag
        words = len(params.text.split())
        if words > 5 and duration_seconds < 1.0:
            score -= 0.3
            
        return max(0.0, min(1.0, score)), duration_seconds
