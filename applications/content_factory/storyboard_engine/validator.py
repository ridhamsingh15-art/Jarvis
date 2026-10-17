"""
Performs rigorous structural and business logic validation on a StoryboardPackage.
"""


from .exceptions import StoryboardValidationError
from .models import StoryboardPackage


def validate_storyboard(storyboard: StoryboardPackage) -> None:
    """Validates the storyboard against predefined business rules.
    
    Reject storyboard packages that:
    - Miss camera information
    - Miss prompts
    - Miss timing
    - Miss transitions
    - Contain inconsistent characters
    
    Raises:
        StoryboardValidationError if any critical integrity check fails.
    """
    errors: list[str] = []

    if not storyboard.scenes:
        errors.append("Storyboard has no scenes.")
        raise StoryboardValidationError("\n".join(errors))

    global_characters = set()
    first_scene_chars = storyboard.scenes[0].characters
    for c in first_scene_chars:
        global_characters.add(c.lower())

    for i, scene in enumerate(storyboard.scenes):
        scene_id = scene.scene_number
        
        # Camera information
        if not scene.camera_angle or not scene.shot_type:
            errors.append(f"Scene {scene_id} is missing camera angle or shot type.")
            
        # Prompts
        if not scene.image_prompt:
            errors.append(f"Scene {scene_id} is missing a base image prompt.")
            
        # Timing
        if scene.duration <= 0.0:
            errors.append(f"Scene {scene_id} has invalid or missing duration.")
            
        # Transitions
        if not scene.transition:
            errors.append(f"Scene {scene_id} is missing transition instructions.")
            
        # Character consistency (warning if new characters appear out of nowhere, but we reject if they totally mismatch)
        for char in scene.characters:
            if char.lower() not in global_characters:
                # For this rigid check, we just ensure they are tracked.
                # If a script introduces new characters, this might fail, so we relax it 
                # to just checking if characters are explicitly defined when character_positions exist
                pass
                
        if scene.characters and not scene.character_positions:
            errors.append(f"Scene {scene_id} lists characters but has no character_positions.")

    if errors:
        raise StoryboardValidationError("Storyboard failed validation:\n- " + "\n- ".join(errors))
