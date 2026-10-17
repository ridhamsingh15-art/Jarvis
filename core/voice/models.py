from dataclasses import dataclass, field

from core.models import JarvisModel
from core.models.primitives import Identifier, Timestamp

from .enums import AudioState, ConversationState


@dataclass(frozen=True, slots=True)
class AudioFrame(JarvisModel):
    """Immutable representation of binary audio chunk."""
    data: bytes
    timestamp: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class WakeWordResult(JarvisModel):
    """Immutable result of a wake word detection."""
    word: str
    confidence: float
    timestamp: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class SpeechResult(JarvisModel):
    """Immutable result of speech-to-text processing."""
    text: str
    confidence: float
    timestamp: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class SpeechResponse(JarvisModel):
    """Immutable synthesized audio response."""
    text: str
    audio_data: bytes
    timestamp: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class VoiceSession(JarvisModel):
    """Immutable tracking state of a current interaction."""
    session_id: Identifier
    state: ConversationState = ConversationState.WAITING_FOR_WAKEWORD
    audio_state: AudioState = AudioState.IDLE
    last_active: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class Transcript(JarvisModel):
    """Immutable representation of a transcribed utterance in the session."""
    session_id: Identifier
    text: str
    is_final: bool = True
    timestamp: Timestamp = field(default_factory=Timestamp)
