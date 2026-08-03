class VoiceError(Exception):
    """Base exception for the voice subsystem."""

class MicrophoneError(VoiceError):
    """Raised when there is an issue with audio input capture."""

class SpeakerError(VoiceError):
    """Raised when there is an issue with audio playback."""

class VADError(VoiceError):
    """Raised when Voice Activity Detection fails."""

class WakeWordError(VoiceError):
    """Raised when Wake Word detection fails."""

class STTError(VoiceError):
    """Raised when Speech-To-Text processing fails."""

class TTSError(VoiceError):
    """Raised when Text-To-Speech generation fails."""
