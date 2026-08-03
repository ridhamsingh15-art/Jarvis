from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from .models import AudioFrame, SpeechResponse, SpeechResult, WakeWordResult


class MicrophoneProvider(ABC):
    """Abstract interface for hardware audio capture."""

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def listen(self) -> AsyncGenerator[AudioFrame, None]:
        pass


class SpeakerProvider(ABC):
    """Abstract interface for hardware audio playback."""

    @abstractmethod
    async def play(self, audio_data: bytes) -> None:
        pass
        
    @abstractmethod
    def stop(self) -> None:
        pass


class VADProvider(ABC):
    """Abstract interface for Voice Activity Detection."""

    @abstractmethod
    def is_speech(self, frame: AudioFrame) -> bool:
        pass


class WakeWordProvider(ABC):
    """Abstract interface for Wake Word detection."""

    @abstractmethod
    def detect(self, frame: AudioFrame) -> WakeWordResult | None:
        pass


class STTProvider(ABC):
    """Abstract interface for Speech-to-Text conversion."""

    @abstractmethod
    async def transcribe(self, audio_data: bytes) -> SpeechResult:
        pass


class TTSProvider(ABC):
    """Abstract interface for Text-to-Speech conversion."""

    @abstractmethod
    async def synthesize(self, text: str) -> SpeechResponse:
        pass
