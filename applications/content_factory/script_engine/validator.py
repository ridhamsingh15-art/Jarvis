"""
Performs rigorous structural and business logic validation on a ScriptPackage.
"""


from .exceptions import ScriptValidationError
from .models import ScriptPackage


def validate_script(script: ScriptPackage) -> None:
    """Validates the script against predefined business rules.
    
    Raises:
        ScriptValidationError if any critical integrity check fails.
    """
    errors: list[str] = []

    # Check top-level fields
    if not script.title or len(script.title) < 5:
        errors.append("Script title is missing or too short.")
    if not script.scenes:
        errors.append("Script has missing scenes (scene list is empty).")

    # Check scene integrity
    expected_scene = 1
    for i, scene in enumerate(script.scenes):
        if scene.scene_number != expected_scene:
            errors.append(f"Scene numbers out of order: expected {expected_scene}, got {scene.scene_number}.")
        
        if not scene.narration.strip():
            errors.append(f"Scene {scene.scene_number} contains empty narration.")
            
        if not scene.image_prompt.strip():
            errors.append(f"Scene {scene.scene_number} has missing prompts (image_prompt is empty).")
            
        expected_scene += 1

    # Check SEO integrity
    if not script.seo:
        errors.append("Script is missing SEO metadata.")
    elif not script.seo.keywords:
        errors.append("Script SEO is missing keywords.")

    if errors:
        raise ScriptValidationError("Script failed validation:\n- " + "\n- ".join(errors))
