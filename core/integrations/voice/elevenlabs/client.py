"""
ElevenLabs API Client.
"""
import logging
import json
import urllib.request
import urllib.error

from core.integrations.voice.models import VoiceRequest, VoiceResponse, ProviderType
from core.integrations.voice.exceptions import SynthesisFailedError, VoiceAuthenticationError

logger = logging.getLogger(__name__)

class ElevenLabsClient:
    """Client for ElevenLabs Text-to-Speech."""

    def __init__(self, api_key: str = "mock_key"):
        self.api_key = api_key
        self.base_url = "https://api.elevenlabs.io/v1"

    def synthesize(self, request: VoiceRequest) -> VoiceResponse:
        """Generate audio using ElevenLabs."""
        logger.info(f"Synthesizing text with ElevenLabs (Voice: {request.voice_id})")
        
        endpoint = f"{self.base_url}/text-to-speech/{request.voice_id}"
        if request.streaming:
            endpoint += "/stream"
            
        payload = {
            "text": request.text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
        
        req = urllib.request.Request(endpoint, method="POST")
        req.add_header("xi-api-key", self.api_key)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "audio/mpeg")
        req.data = json.dumps(payload).encode("utf-8")
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                audio_data = response.read()
                
                if not audio_data:
                    raise SynthesisFailedError("ElevenLabs returned empty audio data.")
                    
                return VoiceResponse(
                    audio_data=audio_data,
                    provider_used=ProviderType.ELEVENLABS,
                    voice_id=request.voice_id,
                    language=request.language
                )
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise VoiceAuthenticationError("Invalid ElevenLabs API key.") from e
            raise SynthesisFailedError(f"ElevenLabs synthesis failed: {e.code} {e.reason}") from e
        except Exception as e:
            raise SynthesisFailedError(f"ElevenLabs request failed: {e}") from e
