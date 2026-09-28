import asyncio

from .interfaces import TTSProvider
from .models import SpeechResponse


class PiperTTSProvider(TTSProvider):
    """Text-to-Speech provider wrapping Piper (mocked for testing)."""

    async def synthesize(self, text: str) -> SpeechResponse:
        # Simulate Piper binary generation delay
        await asyncio.sleep(0.1)
        
        # Generate dummy 16-bit PCM buffer based on text length
        dummy_audio = b"\x01\x00" * (len(text) * 100)
        
        return SpeechResponse(text=text, audio_data=dummy_audio)
