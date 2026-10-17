import asyncio

from .exceptions import SpeakerError
from .interfaces import SpeakerProvider


class DefaultSpeakerProvider(SpeakerProvider):
    """Mock speaker provider simulating playback for testing/CI environments."""

    def __init__(self) -> None:
        self._is_playing = False

    async def play(self, audio_data: bytes) -> None:
        if self._is_playing:
            raise SpeakerError("Speaker is already playing audio.")
            
        self._is_playing = True
        try:
            # Simulate playback duration based on payload size
            # Assuming 16kHz, 16-bit, mono -> 32000 bytes/sec
            duration = len(audio_data) / 32000.0
            await asyncio.sleep(duration)
        finally:
            self._is_playing = False

    def stop(self) -> None:
        self._is_playing = False
