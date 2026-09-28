from .interfaces import OCRProvider, ScreenshotProvider, UIAnalyzerProvider
from .models import ScreenContext


class ScreenContextManager:
    """Orchestrates combining screenshots, OCR, and UI analysis into a unified context."""

    def __init__(
        self,
        screenshot_provider: ScreenshotProvider,
        ocr_provider: OCRProvider,
        ui_analyzer: UIAnalyzerProvider
    ) -> None:
        self._screenshot = screenshot_provider
        self._ocr = ocr_provider
        self._ui = ui_analyzer

    def capture_full_context(self) -> ScreenContext:
        """Captures a screenshot and processes it through OCR and UI analysis."""
        screenshot = self._screenshot.capture_screen()
        
        # Parallel processing could be implemented here in a real environment
        ocr_results = self._ocr.extract_text(screenshot.frame)
        ui_elements = self._ui.analyze(screenshot.frame)
        
        return ScreenContext(
            screenshot=screenshot,
            ocr_results=ocr_results,
            ui_elements=ui_elements
        )
