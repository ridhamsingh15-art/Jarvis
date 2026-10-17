import asyncio

from .interfaces import STTProvider
from .models import SpeechResult


class WhisperSTTProvider(STTProvider):
    """Speech-to-Text provider wrapping Whisper (mocked for testing)."""

    async def transcribe(self, audio_data: bytes) -> SpeechResult:
        # Simulate Whisper.cpp processing delay
        await asyncio.sleep(0.1)
        
        # For testing, if we inject b"TEST_SPEECH", return a fixed transcript.
        if b"TEST_SPEECH" in audio_data:
            return SpeechResult(text="this is a test", confidence=0.9)
            
        # Default mock transcript
        return SpeechResult(text="hello jarvis", confidence=0.85)
