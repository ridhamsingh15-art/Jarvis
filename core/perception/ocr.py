"""
OCR Perception.

Transforms raw bounding boxes and text from the vision layer into
structured, semantically meaningful TextObservations (e.g., preserving
paragraphs, code blocks, headings).
"""
import logging
from core.vision.models import OCRResult
from core.perception.models import TextObservation, SpatialBounds, ObservationType
from core.perception.exceptions import OCRError

logger = logging.getLogger(__name__)

class OCRPerception:
    """Extracts and structures text from raw OCR results."""
    
    def extract_text_observations(self, raw_results: list[OCRResult], image_width: int, image_height: int) -> list[TextObservation]:
        """
        Convert raw OCRResults into semantic TextObservations.
        Uses heuristics to determine if text is a heading or code block.
        """
        try:
            observations = []
            for res in raw_results:
                # Normalize bounds
                bounds = SpatialBounds(
                    x=res.bounding_box.x / image_width if image_width else 0.0,
                    y=res.bounding_box.y / image_height if image_height else 0.0,
                    width=res.bounding_box.width / image_width if image_width else 0.0,
                    height=res.bounding_box.height / image_height if image_height else 0.0
                )
                
                text = res.text.strip()
                if not text:
                    continue
                    
                # Heuristics for formatting
                is_heading = False
                is_code = False
                font_size_hint = "normal"
                
                # If it's a single short line and relatively tall bounding box compared to width, maybe heading
                if len(text) < 50 and "\n" not in text and bounds.height > 0.05:
                    is_heading = True
                    font_size_hint = "large"
                
                # If text contains typical code characters extensively, or indentation
                code_chars = {"{", "}", "def ", "class ", "import ", "=>", "()", ";"}
                if any(c in text for c in code_chars) and "\n" in text:
                    is_code = True
                    
                # Language detection is usually a complex ML task; default to unknown unless explicit
                lang = "unknown"
                
                obs = TextObservation(
                    type=ObservationType.TEXT,
                    confidence=res.confidence,
                    bounds=bounds,
                    text=text,
                    is_heading=is_heading,
                    is_code=is_code,
                    language=lang,
                    font_size_hint=font_size_hint
                )
                observations.append(obs)
                
            return observations
        except Exception as e:
            raise OCRError(f"Failed to process OCR results: {e}") from e
