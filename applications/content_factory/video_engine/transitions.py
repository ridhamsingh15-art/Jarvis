"""
Transitions logic for the Video Engine.
"""

from .models import TransitionConfig


class TransitionBuilder:
    """Calculates and determines transition properties between scenes."""
    
    @staticmethod
    def build_transition(transition_name: str, duration: float = 0.5) -> TransitionConfig:
        """
        Parses a transition name from storyboard (e.g., 'fade', 'crossfade', 'cut')
        into a TransitionConfig.
        """
        if not transition_name:
            return TransitionConfig(transition_type="cut", duration_seconds=0.0)
            
        name = transition_name.lower().strip()
        if "crossfade" in name or "fade" in name:
            return TransitionConfig(transition_type="crossfade", duration_seconds=duration)
            
        return TransitionConfig(transition_type="cut", duration_seconds=0.0)
