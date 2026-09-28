"""
Script structure templates dictating narrative tone and constraints.
"""



def get_template(style: str) -> str:
    """Returns the prompt template constraint for a given script style."""
    style = style.lower()
    
    templates: dict[str, str] = {
        "educational": (
            "Focus on clear pacing, objective explanations, and structured learning. "
            "Use visuals that diagram or illustrate the concepts directly. "
            "Keep the tone informative, authoritative, but approachable."
        ),
        "storytelling": (
            "Focus on narrative hooks, rising action, climax, and resolution. "
            "Visuals should be evocative and cinematic. "
            "Pacing should vary between tense, slow, and fast depending on the beat."
        ),
        "mythology": (
            "Use epic, grand narration. Visuals must be majestic and culturally authentic. "
            "Emphasize scale, divine elements, and deeply philosophical undertones."
        ),
        "technology": (
            "Focus on modern, sleek aesthetics. Narration should be punchy and futuristic. "
            "Visuals should highlight UI/UX, hardware details, or abstract data flows."
        ),
        "motivational": (
            "High energy, inspiring tone. Use fast-paced cuts and intense, emotional visuals. "
            "Narration should be direct, addressing the audience's ambitions."
        ),
        "explainer": (
            "Keep it very simple. Problem -> Solution structure. "
            "Visuals should be clean, possibly vector animations or flat design."
        ),
        "podcast": (
            "Conversational tone. Visuals are secondary, often just a static or simple looping background. "
            "Focus on the depth of the narration and sound design."
        ),
        "tutorial": (
            "Step-by-step instructional structure. Visuals should show exactly what is being discussed on screen. "
            "Pacing must be slow enough for a viewer to follow along."
        )
    }
    
    return templates.get(style, "Use a balanced, engaging structure suitable for general audiences.")
