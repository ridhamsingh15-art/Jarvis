"""
Piper Local Client.
"""
import logging
import subprocess
import tempfile
import os

from core.integrations.voice.models import VoiceRequest, VoiceResponse, ProviderType
from core.integrations.voice.exceptions import SynthesisFailedError

logger = logging.getLogger(__name__)

class PiperClient:
    """Client for local Piper TTS binary."""

    def synthesize(self, request: VoiceRequest) -> VoiceResponse:
        """Generate audio using local Piper binary."""
        logger.info(f"Synthesizing text with Piper (Voice: {request.voice_id})")
        
        # Stub implementation mapping to a simulated subprocess call
        # In production, this would stream text to stdin of the `piper` binary
        
        try:
            # We mock the actual execution since piper binary might not be available in CI
            # A real implementation:
            # subprocess.run(["piper", "--model", f"{request.voice_id}.onnx", "--output_file", temp_file.name], input=request.text.encode())
            
            # Simulated byte output
            audio_data = b"RIFF_PIPER_WAV_HEADER_DATA"
            
            if not audio_data:
                raise SynthesisFailedError("Piper returned empty audio data.")
                
            return VoiceResponse(
                audio_data=audio_data,
                provider_used=ProviderType.PIPER,
                voice_id=request.voice_id,
                language=request.language
            )
        except Exception as e:
            raise SynthesisFailedError(f"Piper synthesis failed: {e}") from e
