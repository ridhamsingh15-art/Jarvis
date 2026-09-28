"""
Generates the raw script JSON using the LLM via ModelRouter.
"""

import json
from typing import Any

from core.model_router import ModelRouter
from providers.capabilities import Capability
from providers.provider_models import InferenceRequirements

from .exceptions import ScriptFormatError
from .templates import get_template


class ScriptGenerator:
    """Invokes the LLM to generate structured script JSON."""

    def __init__(self, model_router: ModelRouter) -> None:
        self._router = model_router

    def generate_raw_script(
        self,
        topic: str,
        style: str,
        additional_context: str = ""
    ) -> dict[str, Any]:
        """Generates the script payload from the LLM and parses it into a dictionary."""
        
        system_prompt = self._build_system_prompt(style)
        user_prompt = f"Topic: {topic}\n\nAdditional Context from Knowledge:\n{additional_context}"
        
        # We require a smart model to generate complex structured JSON
        reqs = InferenceRequirements(
            capabilities=frozenset([Capability.CHAT]),
            task_complexity="high"
        )
        
        response = self._router.generate(system_prompt, user_prompt, requirements=reqs)
        
        return self._extract_json(response.text)

    def _build_system_prompt(self, style: str) -> str:
        template_constraints = get_template(style)
        
        return f"""You are the Master AI Script Writer for a Content Factory.
Your task is to write a production-ready video script in strict JSON format.

Constraints for this style ({style}):
{template_constraints}

You MUST output ONLY a valid JSON object matching the following structure exactly. Do not include markdown formatting (like ```json), just the raw JSON object.

{{
    "title": "String - Catchy title",
    "summary": "String - 1-2 sentence overview",
    "target_audience": "String - Who is this for?",
    "estimated_duration": "String - e.g. 5 minutes",
    "voice_style": "String - Narration tone",
    "music_suggestion": "String - Background track style",
    "seo": {{
        "thumbnail_idea": "String - Visual concept for the thumbnail",
        "keywords": ["List", "of", "strings"],
        "description_draft": "String - YouTube/Instagram description",
        "tags": ["List", "of", "strings"]
    }},
    "scenes": [
        {{
            "scene_number": 1,
            "narration": "String - What the voiceover says",
            "visual_description": "String - What we see on screen",
            "image_prompt": "String - A Midjourney/DALL-E prompt to generate this scene",
            "animation_prompt": "String - Instructions for how the image should move",
            "sound_effects": "String - SFX to play",
            "transition_notes": "String - How we transition to the next scene"
        }}
    ]
}}
"""

    def _extract_json(self, text: str) -> dict[str, Any]:
        """Safely extract and parse JSON from the LLM text."""
        # Clean up any potential markdown wrappers the model might add despite instructions
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        text = text.removesuffix("```")
        text = text.strip()
        
        try:
            return dict(json.loads(text))
        except json.JSONDecodeError as e:
            raise ScriptFormatError(f"Failed to parse LLM output as JSON: {e}\nRaw Text:\n{text}") from e
