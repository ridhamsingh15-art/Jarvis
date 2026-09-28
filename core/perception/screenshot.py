"""
Screenshot Perception Orchestrator.

Captures screenshots using the core Vision system, then delegates to
OCR and UI understanding to build a complete SceneGraph.
"""
import logging
from core.vision.manager import VisionManager
from core.perception.ocr import OCRPerception
from core.perception.ui_understanding import UIUnderstanding
from core.perception.scene_graph import SceneGraphBuilder
from core.perception.models import SceneGraph
from core.perception.exceptions import ScreenshotError

logger = logging.getLogger(__name__)

class ScreenshotPerception:
    """Orchestrates screenshot capture and perception."""

    def __init__(self, vision_manager: VisionManager, ocr: OCRPerception, ui: UIUnderstanding, scene_builder: SceneGraphBuilder):
        self._vision = vision_manager
        self._ocr = ocr
        self._ui = ui
        self._scene_builder = scene_builder

    def perceive_screen(self) -> SceneGraph:
        """Capture full screen and perceive."""
        try:
            context = self._vision.capture_screen()
            width = context.screenshot.frame.width
            height = context.screenshot.frame.height
            
            # Use raw results from the ScreenContext, which already ran OCR and UI analysis
            text_obs = self._ocr.extract_text_observations(context.ocr_results, width, height)
            ui_obs = self._ui.analyze_ui_elements(context.ui_elements, width, height)
            
            all_obs = text_obs + ui_obs
            scene_graph = self._scene_builder.build(all_obs)
            
            return scene_graph
        except Exception as e:
            raise ScreenshotError(f"Failed to perceive screen: {e}") from e

    def perceive_window(self, window_title: str) -> SceneGraph:
        """Capture specific window and perceive."""
        try:
            screenshot = self._vision.capture_window(window_title)
            width = screenshot.frame.width
            height = screenshot.frame.height
            
            raw_ocr = self._vision.read_text(screenshot)
            raw_ui = self._vision.analyze_ui(screenshot)
            
            text_obs = self._ocr.extract_text_observations(raw_ocr, width, height)
            ui_obs = self._ui.analyze_ui_elements(raw_ui, width, height)
            
            all_obs = text_obs + ui_obs
            scene_graph = self._scene_builder.build(all_obs)
            
            return scene_graph
        except Exception as e:
            raise ScreenshotError(f"Failed to perceive window '{window_title}': {e}") from e
