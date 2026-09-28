from .interfaces import VADProvider
from .models import AudioFrame


class DefaultVADProvider(VADProvider):
    """Simple VAD provider evaluating frame energy (mocked for testing)."""

    def __init__(self, threshold: int = 500) -> None:
        self._threshold = threshold

    def is_speech(self, frame: AudioFrame) -> bool:
        # In a real VAD, we'd use WebRTCVAD or Silero.
        # Here we do a basic amplitude check on 16-bit PCM.
        if not frame.data:
            return False
            
        # Quick and naive energy calculation for the stub
        max_amplitude = max((abs(int.from_bytes(frame.data[i:i+2], byteorder='little', signed=True)) for i in range(0, len(frame.data), 2)), default=0)
        return max_amplitude > self._threshold
