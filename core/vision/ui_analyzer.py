import builtins

from .enums import UIElementType
from .interfaces import UIAnalyzerProvider
from .models import BoundingBox, ImageFrame, UIElement


class DefaultUIAnalyzer(UIAnalyzerProvider):
    """Provides UI element extraction capabilities (mocked for testing)."""

    def analyze(self, image: ImageFrame) -> builtins.list[UIElement]:
        if not image.data:
            return []
            
        # Mocked generation
        if b"UI" in image.data:
            return [
                UIElement(
                    type=UIElementType.BUTTON,
                    text="Submit",
                    bounding_box=BoundingBox(x=500, y=500, width=120, height=40),
                    state={"enabled": "true"}
                )
            ]
            
        return []
