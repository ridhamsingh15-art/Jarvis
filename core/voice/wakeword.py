from .interfaces import WakeWordProvider
from .models import AudioFrame, WakeWordResult


class OpenWakeWordProvider(WakeWordProvider):
    """Wake Word provider abstracting OpenWakeWord (mocked for testing)."""

    def __init__(self, target_word: str = "jarvis", threshold: float = 0.5) -> None:
        self._target_word = target_word
        self._threshold = threshold
        # Internal buffer for the mock to simulate sequential matching
        self._buffer: bytearray = bytearray()

    def detect(self, frame: AudioFrame) -> WakeWordResult | None:
        # In a real integration, we pass the frame.data into openwakeword model
        # For mock/testing, we look for a magic byte sequence if injected, else None.
        self._buffer.extend(frame.data)
        
        # Keep buffer bounded
        if len(self._buffer) > 32000:
            self._buffer = self._buffer[-32000:]
            
        # Simulate detection if magic sequence b"WAKEWORD" is found
        if b"WAKEWORD" in self._buffer:
            self._buffer.clear()
            return WakeWordResult(word=self._target_word, confidence=0.95)
            
        return None
