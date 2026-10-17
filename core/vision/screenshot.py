from .exceptions import ScreenshotError
from .interfaces import ScreenshotProvider
from .models import BoundingBox, ImageFrame, Screenshot


class MSSScreenshotProvider(ScreenshotProvider):
    """Provides screenshot capabilities using mss (mocked for testing)."""

    def capture_screen(self) -> Screenshot:
        # Mocked generation
        frame = ImageFrame(data=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", width=1920, height=1080)
        return Screenshot(frame=frame, window_title="Desktop")

    def capture_window(self, window_title: str) -> Screenshot:
        if not window_title:
            raise ScreenshotError("Window title cannot be empty.")
            
        frame = ImageFrame(data=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", width=800, height=600)
        return Screenshot(frame=frame, window_title=window_title)

    def capture_region(self, region: BoundingBox) -> Screenshot:
        if region.width <= 0 or region.height <= 0:
            raise ScreenshotError(f"Invalid region dimensions: {region.width}x{region.height}")
            
        frame = ImageFrame(data=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", width=region.width, height=region.height)
        return Screenshot(frame=frame, window_title="Region Capture")
