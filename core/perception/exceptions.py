class PerceptionError(Exception):
    """Base exception for the Multimodal Perception Engine."""

class OCRError(PerceptionError):
    """Raised when text extraction fails or returns malformed data."""

class UIDetectionError(PerceptionError):
    """Raised when UI element analysis fails."""

class DocumentParsingError(PerceptionError):
    """Raised when structured document parsing fails."""

class VisionError(PerceptionError):
    """Raised when general image understanding fails."""

class ScreenshotError(PerceptionError):
    """Raised when capturing a screenshot or window fails."""
