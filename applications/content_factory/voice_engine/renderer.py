"""
Renderer for the Voice Engine.
"""

from .adapters import VoiceAdapterFactory
from .models import VoiceParameters


class VoiceRenderer:
    """Handles adapter delegation and byte rendering."""
    
    def render(self, model_name: str, params: VoiceParameters) -> bytes:
        """
        Retrieves the correct adapter and generates the voice.
        """
        adapter = VoiceAdapterFactory.get_adapter(model_name)
        return adapter.generate(params)
