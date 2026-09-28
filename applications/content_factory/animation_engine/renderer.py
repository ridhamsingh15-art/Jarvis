"""
Renderer for the Animation Engine.
"""

from typing import Tuple

from .adapters import AnimationAdapterFactory
from .models import AnimationParameters


class AnimationRenderer:
    """Handles adapter delegation and byte rendering."""
    
    def render(self, model_name: str, params: AnimationParameters) -> bytes:
        """
        Retrieves the correct adapter and generates the animation.
        """
        adapter = AnimationAdapterFactory.get_adapter(model_name)
        return adapter.generate(params)
