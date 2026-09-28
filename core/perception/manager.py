"""
Multimodal Perception Engine Manager.

Facade for the perception subsystem, providing cognitive reasoning systems
with high-level semantic observations.
"""
import logging
from core.vision.manager import VisionManager
from core.perception.ocr import OCRPerception
from core.perception.ui_understanding import UIUnderstanding
from core.perception.scene_graph import SceneGraphBuilder
from core.perception.document import DocumentUnderstanding
from core.perception.vision import ImageUnderstanding
from core.perception.screenshot import ScreenshotPerception
from core.perception.observers import PerceptionObservers
from core.perception.models import SceneGraph, DocumentObservation, ImageObservation

logger = logging.getLogger(__name__)

class PerceptionManager:
    """Central facade for the Multimodal Perception Engine."""

    def __init__(self, vision_manager: VisionManager):
        self._vision = vision_manager
        
        # Build subsystem instances
        self._ocr = OCRPerception()
        self._ui = UIUnderstanding()
        self._scene_builder = SceneGraphBuilder()
        
        screenshot_perception = ScreenshotPerception(self._vision, self._ocr, self._ui, self._scene_builder)
        document_perception = DocumentUnderstanding()
        image_perception = ImageUnderstanding()
        
        self._observers = PerceptionObservers(screenshot_perception, document_perception, image_perception)

    def perceive_screen(self) -> SceneGraph:
        """Capture and semantically perceive the full screen."""
        logger.info("PerceptionManager: Perceiving full screen...")
        return self._observers.screenshot.perceive_screen()

    def perceive_window(self, window_title: str) -> SceneGraph:
        """Capture and semantically perceive a specific window."""
        logger.info(f"PerceptionManager: Perceiving window '{window_title}'...")
        return self._observers.screenshot.perceive_window(window_title)

    def perceive_document(self, file_path: str) -> list[DocumentObservation]:
        """Parse a structured document."""
        logger.info(f"PerceptionManager: Perceiving document '{file_path}'...")
        return self._observers.document.analyze_document(file_path)

    def perceive_image(self, image_data: bytes) -> list[ImageObservation]:
        """Perform general image understanding."""
        logger.info("PerceptionManager: Perceiving image data...")
        return self._observers.vision.analyze_image(image_data)
