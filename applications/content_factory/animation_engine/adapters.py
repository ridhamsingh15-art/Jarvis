"""
Model adapters for the Animation Engine.
"""

from typing import Protocol
from .models import AnimationParameters
from .exceptions import AnimationAdapterError
from .comfyui_adapter import ProductionComfyUIAnimationAdapter


class AnimationAdapter(Protocol):
    """Protocol for animation model adapters."""
    
    def generate(self, params: AnimationParameters) -> bytes:
        """Generates animation bytes given the parameters."""
        ...


class WanAdapter:
    """Adapter for WAN video generation."""
    
    def generate(self, params: AnimationParameters) -> bytes:
        if not params.motion_prompt:
            raise AnimationAdapterError("WAN requires a motion_prompt")
        # Mocking WAN generation
        return b"WAN_VIDEO_DATA"


class KlingAdapter:
    """Adapter for Kling video generation."""
    
    def generate(self, params: AnimationParameters) -> bytes:
        if not params.motion_prompt:
            raise AnimationAdapterError("Kling requires a motion_prompt")
        # Mocking Kling generation
        return b"KLING_VIDEO_DATA"


class RunwayAdapter:
    """Adapter for Runway Gen-3 generation."""
    
    def generate(self, params: AnimationParameters) -> bytes:
        if not params.motion_prompt:
            raise AnimationAdapterError("Runway requires a motion_prompt")
        # Mocking Runway generation
        return b"RUNWAY_VIDEO_DATA"


class ComfyUIAnimationAdapter:
    """Adapter for local ComfyUI animation workflows (e.g. AnimateDiff)."""
    
    def generate(self, params: AnimationParameters) -> bytes:
        if not params.motion_prompt:
            raise AnimationAdapterError("ComfyUI requires a motion_prompt")
        # Mocking ComfyUI generation
        return b"COMFYUI_VIDEO_DATA"


class AnimationAdapterFactory:
    """Factory to retrieve the appropriate adapter by name."""
    
    @staticmethod
    def get_adapter(model_name: str) -> AnimationAdapter:
        adapters = {
            "wan": WanAdapter(),
            "kling": KlingAdapter(),
            "runway": RunwayAdapter(),
            "comfyui_animation": ProductionComfyUIAnimationAdapter()
        }
        
        if model_name not in adapters:
            raise AnimationAdapterError(f"Unsupported animation model: {model_name}")
            
        return adapters[model_name]
