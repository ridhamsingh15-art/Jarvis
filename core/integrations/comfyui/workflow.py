"""
ComfyUI Workflow Helpers.

Provides utilities for parsing, modifying, and preparing JSON workflows.
"""
from typing import Any, Dict
from .models import ComfyUIWorkflow

class WorkflowHelper:
    """Helper methods for manipulating ComfyUI workflow JSON."""
    
    @staticmethod
    def inject_seed(workflow: ComfyUIWorkflow, seed: int) -> ComfyUIWorkflow:
        """Find nodes that take a seed and inject the given seed."""
        nodes = dict(workflow.nodes)
        for node_id, node_data in nodes.items():
            if "inputs" in node_data and "seed" in node_data["inputs"]:
                node_data["inputs"]["seed"] = seed
            elif "inputs" in node_data and "noise_seed" in node_data["inputs"]:
                node_data["inputs"]["noise_seed"] = seed
        return ComfyUIWorkflow(nodes=nodes)
        
    @staticmethod
    def set_text_prompt(workflow: ComfyUIWorkflow, text: str, node_type: str = "CLIPTextEncode") -> ComfyUIWorkflow:
        """Inject a text prompt into the first matching node type."""
        nodes = dict(workflow.nodes)
        for node_id, node_data in nodes.items():
            if node_data.get("class_type") == node_type:
                if "inputs" in node_data and "text" in node_data["inputs"]:
                    node_data["inputs"]["text"] = text
                    break
        return ComfyUIWorkflow(nodes=nodes)
