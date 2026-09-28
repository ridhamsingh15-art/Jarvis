"""
Adapters for generating model-specific image/video prompts from a generic scene description.
"""

from abc import ABC, abstractmethod


class PromptAdapter(ABC):
    """Base interface for transforming generic scene concepts into model-specific prompts."""
    
    @abstractmethod
    def generate_prompt(self, base_prompt: str, style: str, shot_type: str, lighting: str, negative: str = "") -> str:
        """Returns the optimized positive prompt string."""


class FluxAdapter(PromptAdapter):
    """Optimizes prompts for Flux (Black Forest Labs).
    Flux prefers natural language, highly descriptive, caption-like structures.
    """
    def generate_prompt(self, base_prompt: str, style: str, shot_type: str, lighting: str, negative: str = "") -> str:
        # Flux rarely needs negative prompts, but benefits from explicit photography terms
        style_desc = f"in the style of {style}" if style else "photorealistic"
        return f"A {shot_type} of {base_prompt}. The lighting is {lighting}. {style_desc}, highly detailed, 8k resolution, professional cinematography."


class SDXLAdapter(PromptAdapter):
    """Optimizes prompts for Stable Diffusion XL.
    SDXL works well with comma-separated tags, medium/style keywords at the end.
    """
    def generate_prompt(self, base_prompt: str, style: str, shot_type: str, lighting: str, negative: str = "") -> str:
        style_tag = f"{style} style" if style else "cinematic photography"
        return f"{base_prompt}, {shot_type}, {lighting}, {style_tag}, masterpiece, best quality, highly detailed"


class ComfyUIAdapter(PromptAdapter):
    """Optimizes prompts for complex ComfyUI workflows (typically SD 1.5 or SDXL based, but highly tagged).
    Usually paired with Loras or control nets, so explicit mechanical descriptions help.
    """
    def generate_prompt(self, base_prompt: str, style: str, shot_type: str, lighting: str, negative: str = "") -> str:
        return f"(masterpiece, best quality:1.2), {shot_type}, {base_prompt}, (lighting: {lighting}:1.1), (style: {style}:1.1), detailed background"


class WANAdapter(PromptAdapter):
    """Optimizes prompts for WAN (Video Generation).
    Requires explicit motion, camera movement, and temporal consistency descriptions.
    """
    def generate_prompt(self, base_prompt: str, style: str, shot_type: str, lighting: str, negative: str = "") -> str:
        # We assume the engine will append actual camera motion later, but we set the base up.
        style_desc = f"Visual style: {style}." if style else ""
        return f"{shot_type}. {base_prompt}. {lighting} lighting. {style_desc} High quality video, smooth motion, cinematic."


class PromptAdapterRegistry:
    """Registry to easily retrieve adapters."""
    _adapters = {
        "flux": FluxAdapter(),
        "sdxl": SDXLAdapter(),
        "comfyui": ComfyUIAdapter(),
        "wan": WANAdapter()
    }

    @classmethod
    def get(cls, model_name: str) -> PromptAdapter:
        return cls._adapters.get(model_name.lower(), SDXLAdapter())  # Default to SDXL
