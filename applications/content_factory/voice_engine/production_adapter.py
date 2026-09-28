"""
Production Voice Adapter.

Bridges the Voice Engine to the core VoiceManager, handling parameter mapping.
"""
import logging
from typing import Optional

from .models import VoiceParameters
from .exceptions import VoiceAdapterError
from core.integrations.voice import (
    VoiceManager, 
    VoiceRequest, 
    ProviderType,
    VoiceIntegrationError
)

logger = logging.getLogger(__name__)

class ProductionVoiceAdapter:
    """Production Adapter for Voice Generation."""
    
    def __init__(self, provider_str: str):
        self.manager = VoiceManager()
        self.provider = self._map_provider(provider_str)

    def _map_provider(self, provider_str: str) -> ProviderType:
        provider_map = {
            "elevenlabs": ProviderType.ELEVENLABS,
            "xtts": ProviderType.XTTS,
            "piper": ProviderType.PIPER,
            "kokoro": ProviderType.PIPER # fallback since kokoro not in core yet
        }
        return provider_map.get(provider_str, ProviderType.PIPER)

    def generate(self, params: VoiceParameters) -> bytes:
        """Executes the generation request via VoiceManager."""
        if not params.text:
            raise VoiceAdapterError("Production adapter requires text to generate.")
            
        logger.info(f"Routing voice request to VoiceManager (Provider: {self.provider.value})")
        
        request = VoiceRequest(
            text=params.text,
            provider=self.provider,
            voice_id=params.voice_id or "default",
            language=params.language or "en",
            streaming=False,
            allow_fallback=True
        )
        
        try:
            response = self.manager.generate(request)
            logger.info(f"Generation successful. Actual provider used: {response.provider_used.value}")
            return response.audio_data
        except VoiceIntegrationError as e:
            raise VoiceAdapterError(f"Generation failed: {e}") from e
