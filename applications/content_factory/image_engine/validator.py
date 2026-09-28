"""
Validates the structural integrity of a generated image metadata payload.
"""

from .exceptions import ImageValidationError
from .models import ImageMetadata


class ImageValidator:
    """Validates the resulting image metadata before ingestion."""

    def validate(self, metadata: ImageMetadata) -> None:
        """
        Ensures the metadata represents a valid generation.
        """
        errors = []
        
        if not metadata.prompt:
            errors.append("Missing prompt.")
            
        if not metadata.generation_model:
            errors.append("Missing generation model.")
            
        if metadata.scene_number < 1:
            errors.append("Invalid scene number.")
            
        if metadata.generation_time <= 0:
            errors.append("Invalid generation time.")
            
        if errors:
            raise ImageValidationError("Image Validation Failed:\n- " + "\n- ".join(errors))
