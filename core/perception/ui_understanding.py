"""
UI Understanding.

Translates raw UIElements from the vision layer into semantic
UIObservations with recognized roles (e.g., dialogs, editors, terminals).
"""
import logging
from core.vision.models import UIElement
from core.perception.models import UIObservation, SpatialBounds, ObservationType, UIComponentRole
from core.perception.exceptions import UIDetectionError
from core.vision.enums import UIElementType

logger = logging.getLogger(__name__)

class UIUnderstanding:
    """Parses UI layouts and elements into structured semantic observations."""

    def analyze_ui_elements(self, raw_elements: list[UIElement], image_width: int, image_height: int) -> list[UIObservation]:
        """
        Convert raw UI elements into semantic UIObservations.
        """
        try:
            observations = []
            for el in raw_elements:
                bounds = SpatialBounds(
                    x=el.bounding_box.x / image_width if image_width else 0.0,
                    y=el.bounding_box.y / image_height if image_height else 0.0,
                    width=el.bounding_box.width / image_width if image_width else 0.0,
                    height=el.bounding_box.height / image_height if image_height else 0.0
                )
                
                # Map core.vision UIElementType to UIComponentRole
                role = self._map_role(el.type, el.text)
                
                # Extract state if present
                state = el.state.get("status", "default")
                interactive = el.state.get("interactive", "true").lower() == "true"
                
                obs = UIObservation(
                    type=ObservationType.UI,
                    confidence=1.0, # Vision UI elements don't currently expose confidence natively
                    bounds=bounds,
                    role=role,
                    label=el.text or "",
                    state=state,
                    interactive=interactive,
                    context="" # Context could be enriched later by scene graph
                )
                observations.append(obs)
                
            return observations
        except Exception as e:
            raise UIDetectionError(f"Failed to analyze UI elements: {e}") from e

    def _map_role(self, element_type: UIElementType, text: str | None) -> UIComponentRole:
        text_lower = (text or "").lower()
        
        if element_type == UIElementType.BUTTON:
            return UIComponentRole.BUTTON
        elif element_type == UIElementType.TEXT_FIELD:
            return UIComponentRole.EDITOR
        elif element_type == UIElementType.MENU:
            return UIComponentRole.MENU
        elif element_type == UIElementType.WINDOW:
            if "terminal" in text_lower or "cmd" in text_lower or "powershell" in text_lower or "bash" in text_lower:
                return UIComponentRole.TERMINAL
            if "browser" in text_lower or "chrome" in text_lower or "edge" in text_lower or "firefox" in text_lower:
                return UIComponentRole.BROWSER
            if "error" in text_lower or "exception" in text_lower:
                return UIComponentRole.ERROR
            return UIComponentRole.DIALOG
        elif element_type == UIElementType.STATUS_BAR:
            if "error" in text_lower or "failed" in text_lower:
                return UIComponentRole.ERROR
            if "warning" in text_lower:
                return UIComponentRole.WARNING
            return UIComponentRole.INFO
            
        return UIComponentRole.UNKNOWN
