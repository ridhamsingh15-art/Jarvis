"""
Health checking utilities for Voice Providers.
"""
import logging
import urllib.request
import urllib.error
from .exceptions import VoiceProviderOfflineError

logger = logging.getLogger(__name__)

class ProviderHealthCheck:
    """Checks the health of various voice providers."""

    @staticmethod
    def check_elevenlabs() -> bool:
        """Pings the ElevenLabs API."""
        try:
            req = urllib.request.Request("https://api.elevenlabs.io/v1/voices")
            # We don't authenticate, we just expect a 401 or 200, but not a timeout/conn error
            with urllib.request.urlopen(req, timeout=5) as response:
                return True
        except urllib.error.HTTPError:
            # An HTTP error means the server is up
            return True
        except Exception as e:
            logger.warning(f"ElevenLabs health check failed: {e}")
            raise VoiceProviderOfflineError("ElevenLabs is offline or unreachable.") from e

    @staticmethod
    def check_xtts(host: str = "127.0.0.1", port: int = 8020) -> bool:
        """Pings a local XTTS server."""
        try:
            url = f"http://{host}:{port}/health"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as response:
                return True
        except Exception as e:
            logger.warning(f"XTTS health check failed: {e}")
            raise VoiceProviderOfflineError("XTTS is offline or unreachable.") from e

    @staticmethod
    def check_piper() -> bool:
        """Checks if the local Piper binary is accessible."""
        # Stub: check if `piper` is in PATH or valid wrapper exists
        return True
