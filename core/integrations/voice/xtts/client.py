"""
XTTS Local Client.
"""
import logging
import json
import urllib.request
import urllib.error

from core.integrations.voice.models import VoiceRequest, VoiceResponse, ProviderType
from core.integrations.voice.exceptions import SynthesisFailedError

logger = logging.getLogger(__name__)

class XTTSClient:
    """Client for local XTTS API."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8020):
        self.base_url = f"http://{host}:{port}"

    def synthesize(self, request: VoiceRequest) -> VoiceResponse:
        """Generate audio using XTTS."""
        logger.info(f"Synthesizing text with XTTS (Voice: {request.voice_id})")
        
        endpoint = f"{self.base_url}/tts"
        payload = {
            "text": request.text,
            "speaker_wav": request.voice_id,  # In XTTS, voice_id is often a path to a reference WAV
            "language": request.language
        }
        
        req = urllib.request.Request(endpoint, method="POST")
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(payload).encode("utf-8")
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                audio_data = response.read()
                
                if not audio_data:
                    raise SynthesisFailedError("XTTS returned empty audio data.")
                    
                return VoiceResponse(
                    audio_data=audio_data,
                    provider_used=ProviderType.XTTS,
                    voice_id=request.voice_id,
                    language=request.language
                )
        except Exception as e:
            raise SynthesisFailedError(f"XTTS synthesis failed: {e}") from e
