"""
Evaluates script quality against narrative constraints.
"""

from .exceptions import ScriptQualityError
from .models import ScriptPackage


def evaluate_quality(script: ScriptPackage) -> float:
    """Evaluates the script quality heuristically.
    
    Returns:
        A score between 0.0 and 100.0
        
    Raises:
        ScriptQualityError if the score falls below a critical threshold.
    """
    score = 100.0

    # Timing heuristic: generally expect around 120-150 words per minute.
    # A short duration (e.g. 5 minutes) should have 600-750 words.
    total_words = sum(len(scene.narration.split()) for scene in script.scenes)
    
    if total_words < 50:
        score -= 40  # Extremely short, likely lacks depth
    elif total_words < 200:
        score -= 20  # A bit thin

    # Scene flow heuristic: ensure scenes have visual descriptions to match the words
    visual_balance = sum(len(scene.visual_description.split()) for scene in script.scenes)
    if visual_balance < total_words * 0.1:
        # Visuals are less than 10% of narration length; likely just talking heads or static
        score -= 15

    # Hook quality heuristic: Scene 1 should ideally be punchy (not too long)
    if script.scenes:
        first_scene_words = len(script.scenes[0].narration.split())
        if first_scene_words > 100:
            # Too much exposition before a cut
            score -= 10

    # Ensure there is a music suggestion and voice style
    if not script.voice_style.strip():
        score -= 5
    if not script.music_suggestion.strip():
        score -= 5

    # SEO checks
    if script.seo:
        if len(script.seo.description_draft.split()) < 10:
            score -= 5
        if len(script.seo.tags) < 3:
            score -= 5

    if score < 70.0:
        raise ScriptQualityError(f"Script quality review failed with score {score}/100.")
        
    return score
