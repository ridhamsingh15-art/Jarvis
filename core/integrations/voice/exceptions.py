"""
Exceptions for the Voice Integration.
"""

class VoiceIntegrationError(Exception):
    """Base exception for the Voice Integration subsystem."""

class VoiceProviderOfflineError(VoiceIntegrationError):
    """Raised when a voice provider API or local server is unreachable."""

class SynthesisFailedError(VoiceIntegrationError):
    """Raised when text-to-speech synthesis fails."""

class VoiceAuthenticationError(VoiceIntegrationError):
    """Raised when provider authentication fails."""
