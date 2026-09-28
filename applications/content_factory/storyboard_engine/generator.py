"""
Generates the raw storyboard JSON using the LLM via ModelRouter.
"""

import json
from typing import Any

from applications.content_factory.script_engine.models import ScriptPackage
from core.model_router import ModelRouter
from providers.capabilities import Capability
from providers.provider_models import InferenceRequirements

from .exceptions import StoryboardFormatError


class StoryboardGenerator:
    """Invokes the LLM to expand a ScriptPackage into a detailed Storyboard JSON."""

    def __init__(self, model_router: ModelRouter) -> None:
        self._router = model_router

    def generate_raw_storyboard(self, script: ScriptPackage, visual_style: str = "") -> dict[str, Any]:
        """Expands the entire script into a storyboard JSON payload."""
        
        system_prompt = self._build_system_prompt(visual_style)
        
        # Serialize the ScriptPackage to pass to the LLM
        import dataclasses
        script_dict = dataclasses.asdict(script)
        user_prompt = f"Expand this script into a complete storyboard:\n\n{json.dumps(script_dict, indent=2)}"
        
        # We require a smart model to generate complex structured JSON and massive context
        reqs = InferenceRequirements(
            capabilities=frozenset([Capability.CHAT]),
            task_complexity="high"
        )
        
        response = self._router.generate(system_prompt, user_prompt, requirements=reqs)
        
        return self._extract_json(response.text, script.title, visual_style)

    def _build_system_prompt(self, visual_style: str) -> str:
        style_instruction = f"The visual style is {visual_style}." if visual_style else "Determine the best visual style based on the script."
        
        return f"""You are the Master AI Storyboard Artist for a Content Factory.
Your task is to take a complete ScriptPackage and expand EVERY scene into highly detailed production instructions.

{style_instruction}

You MUST output ONLY a valid JSON object matching the following structure exactly. 
EVERY single field must be populated for EVERY scene. Do not omit any fields.

{{
    "scenes": [
        {{
            "scene_number": 1,
            "narration": "String - Match script",
            "dialogue": "String - Any dialogue, or empty string",
            "duration": 5.0, // Float, estimated duration in seconds
            "camera_angle": "String - e.g. Wide Shot, Close Up, POV, Low Angle",
            "camera_movement": "String - e.g. Static, Pan Left, Tracking, Drone",
            "composition": "String - e.g. Rule of thirds, Center framed",
            "shot_type": "String - e.g. Establishing, Medium, Macro",
            "lighting": "String - e.g. Cinematic, Volumetric, High key",
            "time_of_day": "String - e.g. Sunset, Night, Golden hour",
            "environment": "String - e.g. Interior, Exterior",
            "location": "String - Specific setting name",
            "characters": ["List of character names"],
            "character_positions": "String - Where they stand",
            "character_expressions": "String - Emotion/Face",
            "character_motion": "String - Actions they perform",
            "props": ["List of important objects"],
            "background": "String - What is behind the subject",
            "foreground": "String - What is in front of the subject",
            "color_palette": ["Hex codes or color names"],
            "mood": "String - Emotional tone of the scene",
            "visual_style": "String - e.g. Photorealistic, Anime, 3D",
            "animation_notes": "String - Instructions for video generation",
            "transition": "String - e.g. Cut, Crossfade, Whip pan",
            "sound_effects": "String - SFX",
            "music_cue": "String - Music notes",
            "voice_timing": "String - e.g. Starts immediately, Pause after 2s",
            "image_prompt": "String - A highly detailed generic prompt for image generation",
            "negative_prompt": "String - What to avoid",
            "thumbnail_candidate": false // Boolean, true if this is the best scene for a thumbnail
        }}
    ]
}}
"""

    def _extract_json(self, text: str, title: str, style: str) -> dict[str, Any]:
        """Safely extract and parse JSON from the LLM text."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        text = text.removesuffix("```")
        text = text.strip()
        
        try:
            data = dict(json.loads(text))
            data["script_title"] = title
            data["visual_style_override"] = style
            return data
        except json.JSONDecodeError as e:
            raise StoryboardFormatError(f"Failed to parse LLM output as JSON: {e}\nRaw Text:\n{text}") from e
