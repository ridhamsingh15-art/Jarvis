import builtins

from .interfaces import OCRProvider
from .models import BoundingBox, ImageFrame, OCRResult


class TesseractOCRProvider(OCRProvider):
    """Provides OCR capabilities using Tesseract (mocked for testing)."""

    def extract_text(self, image: ImageFrame) -> builtins.list[OCRResult]:
        if not image.data:
            return []
            
        # Mocked generation based on dummy byte sequences
        if b"TEXT" in image.data:
            return [
                OCRResult(
                    text="Hello World",
                    bounding_box=BoundingBox(x=10, y=10, width=100, height=20),
                    confidence=0.95
                )
            ]
            
        return []
