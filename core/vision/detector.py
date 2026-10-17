import builtins

from .interfaces import ObjectDetector
from .models import BoundingBox, DetectedObject, ImageFrame


class DefaultObjectDetector(ObjectDetector):
    """Provides object detection capabilities (mocked for testing)."""

    def detect(self, image: ImageFrame) -> builtins.list[DetectedObject]:
        if not image.data:
            return []
            
        # Mocked detection
        if b"OBJECT" in image.data:
            return [
                DetectedObject(
                    label="person",
                    bounding_box=BoundingBox(x=100, y=100, width=50, height=200),
                    confidence=0.88
                )
            ]
            
        return []
