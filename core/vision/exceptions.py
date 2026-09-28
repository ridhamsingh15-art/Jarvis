class VisionError(Exception):
    """Base exception for the vision subsystem."""

class ScreenshotError(VisionError):
    """Raised when there is an issue capturing the screen."""

class OCRError(VisionError):
    """Raised when OCR extraction fails."""

class DetectorError(VisionError):
    """Raised when object detection fails."""

class CameraError(VisionError):
    """Raised when camera capture fails."""

class UIAnalysisError(VisionError):
    """Raised when UI analysis fails."""
