"""
Production ComfyUI Image Adapter.
"""
import logging
from typing import Any

from .models import GenerationParameters
from core.integrations.comfyui import (
    ComfyUIClient,
    ComfyUIWebSocket,
    WorkflowHelper,
    ComfyUIDownloader,
    ComfyUIHealthCheck,
    ComfyUIWorkflow
)

logger = logging.getLogger(__name__)

class ProductionComfyUIAdapter:
    """Production Adapter for ComfyUI Workflows."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8188):
        self.client = ComfyUIClient(host, port)
        self.health_check = ComfyUIHealthCheck(self.client)
        self.websocket = ComfyUIWebSocket(self.client)
        self.downloader = ComfyUIDownloader(self.client)
        
    def get_supported_resolutions(self) -> list[tuple[int, int]]:
        return [(1920, 1080), (1080, 1920), (1024, 1024)]
        
    def format_parameters(self, params: GenerationParameters) -> dict[str, Any]:
        """Translates generic parameters into backend payload."""
        # This mirrors the old mock logic but prepares it for real execution
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
        
    def generate(self, params: GenerationParameters) -> list[bytes]:
        """Executes the workflow against the real ComfyUI server."""
        logger.info("Executing generation via Production ComfyUI...")
        
        # 1. Health check
        self.health_check.check()
        
        # 2. Format workflow
        raw_workflow = self.format_parameters(params)["prompt"]
        workflow = ComfyUIWorkflow(nodes=raw_workflow)
        
        # 3. Queue prompt
        prompt_response = self.client.queue_prompt(workflow)
        prompt_id = prompt_response.prompt_id
        
        # 4. Wait for completion
        self.websocket.wait_for_completion(prompt_id)
        
        # 5. Fetch history & download
        history = self.client.get_history(prompt_id)
        outputs = self.downloader.download_outputs(history)
        
        return [out.data for out in outputs]
