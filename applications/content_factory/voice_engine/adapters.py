"""
Model adapters for the Voice Engine.
"""

from typing import Protocol
from .models import VoiceParameters
from .exceptions import VoiceAdapterError
from .production_adapter import ProductionVoiceAdapter


class VoiceAdapter(Protocol):
    """Protocol for voice generation model adapters."""
    
    def generate(self, params: VoiceParameters) -> bytes:
        """Generates voice audio bytes given the parameters."""
        ...


class ElevenLabsAdapter:
    """Adapter for ElevenLabs voice generation."""
    
    def generate(self, params: VoiceParameters) -> bytes:
        if not params.text:
            raise VoiceAdapterError("ElevenLabs requires text")
        # Mocking generation
        return b"ELEVENLABS_AUDIO_DATA"


class XTTSAdapter:
    """Adapter for XTTS voice generation."""
    
    def generate(self, params: VoiceParameters) -> bytes:
        if not params.text:
            raise VoiceAdapterError("XTTS requires text")
        # Mocking generation
        return b"XTTS_AUDIO_DATA"


class KokoroAdapter:
    """Adapter for Kokoro voice generation."""
    
    def generate(self, params: VoiceParameters) -> bytes:
        if not params.text:
            raise VoiceAdapterError("Kokoro requires text")
        # Mocking generation
        return b"KOKORO_AUDIO_DATA"


class PiperAdapter:
    """Adapter for local Piper voice generation."""
    
    def generate(self, params: VoiceParameters) -> bytes:
        if not params.text:
            raise VoiceAdapterError("Piper requires text")
        # Mocking generation
        return b"PIPER_AUDIO_DATA"


class VoiceAdapterFactory:
    """Factory to retrieve the appropriate adapter by name."""
    
    @staticmethod
    def get_adapter(model_name: str) -> VoiceAdapter:
        adapters = {
            "elevenlabs": ProductionVoiceAdapter("elevenlabs"),
            "xtts": ProductionVoiceAdapter("xtts"),
            "kokoro": ProductionVoiceAdapter("kokoro"),
            "piper": ProductionVoiceAdapter("piper")
        }
        
        # Default to piper if not found for robust local fallback
        if model_name not in adapters:
            return ProductionVoiceAdapter("piper")
            
        return adapters[model_name]
