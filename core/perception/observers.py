"""
Perception Observers.

Aggregates all perception modalities.
"""
import logging
from core.perception.screenshot import ScreenshotPerception
from core.perception.document import DocumentUnderstanding
from core.perception.vision import ImageUnderstanding

logger = logging.getLogger(__name__)

class PerceptionObservers:
    """Aggregates all perception engines."""

    def __init__(self, screenshot: ScreenshotPerception, document: DocumentUnderstanding, vision: ImageUnderstanding):
        self.screenshot = screenshot
        self.document = document
        self.vision = vision
