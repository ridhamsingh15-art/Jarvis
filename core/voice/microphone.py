import asyncio
from collections.abc import AsyncGenerator

from .exceptions import MicrophoneError
from .interfaces import MicrophoneProvider
from .models import AudioFrame


class DefaultMicrophoneProvider(MicrophoneProvider):
    """Mock microphone provider generating silence frames for testing/CI environments."""

    def __init__(self) -> None:
        self._is_recording = False

    def start(self) -> None:
        self._is_recording = True

    def stop(self) -> None:
        self._is_recording = False

    async def listen(self) -> AsyncGenerator[AudioFrame, None]:
        if not self._is_recording:
            raise MicrophoneError("Cannot listen when microphone is not started.")
            
        while self._is_recording:
            # Simulate generating 100ms chunks of 16-bit PCM (dummy zeroes)
            await asyncio.sleep(0.1)
            yield AudioFrame(data=b"\x00" * 3200)
