"""
Voice Manager.

Central routing facade. It accepts a VoiceRequest, checks provider health, 
routes the request, handles retries, and seamlessly falls back to Piper.
"""
import logging
from typing import Optional

from .models import VoiceRequest, VoiceResponse, ProviderType
from .elevenlabs.client import ElevenLabsClient
from .xtts.client import XTTSClient
from .piper.client import PiperClient
from .health import ProviderHealthCheck
from .exceptions import VoiceIntegrationError, VoiceProviderOfflineError, SynthesisFailedError

logger = logging.getLogger(__name__)

class VoiceManager:
    """Manages text-to-speech generation and fallbacks."""

    def __init__(self, elevenlabs_key: str = "mock_key"):
        self.elevenlabs = ElevenLabsClient(elevenlabs_key)
        self.xtts = XTTSClient()
        self.piper = PiperClient()

    def generate(self, request: VoiceRequest) -> VoiceResponse:
        """
        Generate voice based on the request.
        Attempts the requested provider, and falls back to Piper if it fails.
        """
        logger.info(f"Received VoiceRequest for provider {request.provider.value}")
        
        try:
            return self._execute_generation(request)
        except (VoiceProviderOfflineError, SynthesisFailedError) as e:
            logger.error(f"Primary provider failed: {e}")
            if request.allow_fallback and request.provider != ProviderType.PIPER:
                logger.info("Attempting local fallback to Piper...")
                fallback_req = VoiceRequest(
                    text=request.text,
                    provider=ProviderType.PIPER,
                    voice_id="default_piper_voice",
                    language=request.language,
                    streaming=request.streaming,
                    allow_fallback=False
                )
                return self._execute_generation(fallback_req)
            else:
                raise VoiceIntegrationError("Voice generation failed and fallback is disabled or exhausted.") from e

    def _execute_generation(self, request: VoiceRequest) -> VoiceResponse:
        """Helper to route to the correct client after health check."""
        if request.provider == ProviderType.ELEVENLABS:
            ProviderHealthCheck.check_elevenlabs()
            return self.elevenlabs.synthesize(request)
            
        elif request.provider == ProviderType.XTTS:
            ProviderHealthCheck.check_xtts()
            return self.xtts.synthesize(request)
            
        elif request.provider == ProviderType.PIPER:
            ProviderHealthCheck.check_piper()
            return self.piper.synthesize(request)
            
        else:
            raise ValueError(f"Unknown voice provider: {request.provider}")
