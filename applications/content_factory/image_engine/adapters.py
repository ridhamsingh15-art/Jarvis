"""
Image Model Adapters.
"""

from abc import ABC, abstractmethod
from typing import Any

from .models import GenerationParameters
from .comfyui_adapter import ProductionComfyUIAdapter


class ImageAdapter(ABC):
    """Base interface for an Image Generation model backend."""
    
    @abstractmethod
    def get_supported_resolutions(self) -> list[tuple[int, int]]:
        pass
        
    @abstractmethod
    def format_parameters(self, params: GenerationParameters) -> dict[str, Any]:
        """Translates the generic parameters into backend-specific payload."""


class FluxAdapter(ImageAdapter):
    """Adapter for Black Forest Labs Flux."""
    
    def get_supported_resolutions(self) -> list[tuple[int, int]]:
        return [(1920, 1080), (1080, 1920), (1024, 1024)]
        
    def format_parameters(self, params: GenerationParameters) -> dict[str, Any]:
        return {
            "prompt": params.prompt,
            "seed": params.seed,
            "num_inference_steps": params.steps,
            "guidance_scale": params.cfg,
            "width": params.width,
            "height": params.height,
            "model": "flux-1-schnell"
        }


class SDXLAdapter(ImageAdapter):
    """Adapter for Stable Diffusion XL."""
    
    def get_supported_resolutions(self) -> list[tuple[int, int]]:
        return [(1024, 1024), (1152, 896), (896, 1152)]
        
    def format_parameters(self, params: GenerationParameters) -> dict[str, Any]:
        return {
            "prompt": params.prompt,
            "negative_prompt": params.negative_prompt,
            "seed": params.seed,
            "steps": params.steps,
            "cfg_scale": params.cfg,
            "sampler_name": params.sampler,
            "width": params.width,
            "height": params.height
        }


class ComfyUIAdapter(ImageAdapter):
    """Adapter for ComfyUI Workflows."""
    
    def get_supported_resolutions(self) -> list[tuple[int, int]]:
        return [(1920, 1080), (1080, 1920), (1024, 1024)]
        
    def format_parameters(self, params: GenerationParameters) -> dict[str, Any]:
        return {
            "prompt": {
                "3": {
                    "inputs": {
                        "seed": params.seed,
                        "steps": params.steps,
                        "cfg": params.cfg,
                        "sampler_name": params.sampler,
                        "scheduler": "normal",
                        "denoise": 1
                    },
                    "class_type": "KSampler"
                },
                "6": {
                    "inputs": {
                        "text": params.prompt
                    },
                    "class_type": "CLIPTextEncode"
                },
                "7": {
                    "inputs": {
                        "text": params.negative_prompt
                    },
                    "class_type": "CLIPTextEncode"
                }
            }
        }


class ImageAdapterRegistry:
    """Registry to easily retrieve image adapters."""
    _adapters = {
        "flux": FluxAdapter(),
        "sdxl": SDXLAdapter(),
        "comfyui": ProductionComfyUIAdapter()
    }

    @classmethod
    def get(cls, model_name: str) -> ImageAdapter:
        return cls._adapters.get(model_name.lower(), FluxAdapter())
