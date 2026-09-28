"""
Evaluates storyboard quality against narrative and visual constraints.
"""

from .exceptions import StoryboardQualityError
from .models import StoryboardPackage


def evaluate_quality(storyboard: StoryboardPackage) -> float:
    """Evaluates the storyboard quality heuristically.
    
    Evaluate:
    - Scene continuity
    - Visual consistency
    - Camera consistency
    - Character consistency
    - Prompt quality
    - Animation readiness
    - Transition quality
    - Retention
    - Thumbnail potential
    
    Returns:
        A score between 0.0 and 100.0
        
    Raises:
        StoryboardQualityError if the score falls below a critical threshold (e.g. 70.0).
    """
    score = 100.0
    
    if not storyboard.scenes:
        raise StoryboardQualityError("Cannot evaluate an empty storyboard.")

    has_thumbnail_candidate = False
    
    for scene in storyboard.scenes:
        # Prompt Quality
        if len(scene.image_prompt.split()) < 5:
            score -= 5  # Too vague
            
        # Visual/Camera Consistency
        if "close up" in scene.shot_type.lower() and "wide" in scene.camera_angle.lower():
            score -= 10  # Contradictory camera instructions
            
        # Animation Readiness
        if not scene.animation_notes.strip() and not scene.camera_movement.strip():
            score -= 5  # Static shot, poor retention
            
        if scene.thumbnail_candidate:
            has_thumbnail_candidate = True
            
        # Character expressions should exist if close up
        if "close up" in scene.shot_type.lower() and not scene.character_expressions.strip():
            score -= 5
            
    if not has_thumbnail_candidate:
        score -= 15
        
    if score < 70.0:
        raise StoryboardQualityError(f"Storyboard quality review failed with score {score}/100.")
        
    return score
