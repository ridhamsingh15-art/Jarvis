import asyncio
from collections.abc import AsyncGenerator

from .exceptions import CameraError
from .interfaces import CameraProvider
from .models import ImageFrame


class OpenCVCameraProvider(CameraProvider):
    """Provides camera capture capabilities using OpenCV (mocked for testing)."""

    def __init__(self) -> None:
        self._is_running = False

    def start(self) -> None:
        self._is_running = True

    def stop(self) -> None:
        self._is_running = False

    async def get_frame(self) -> AsyncGenerator[ImageFrame, None]:
        if not self._is_running:
            raise CameraError("Cannot capture frames while camera is not started.")
            
        while self._is_running:
            await asyncio.sleep(0.033)  # ~30fps mock
            yield ImageFrame(
                data=b"\xFF\xD8\xFF\xE0\x00\x10JFIF",  # Dummy JPEG header
                width=640,
                height=480,
                format="JPEG"
            )
