"""
Physical rendering logic for Image Generation.
"""

import os
import tempfile
import time

from .adapters import ImageAdapterRegistry
from .exceptions import ImageAdapterError
from .models import GenerationTask


class ImageRenderer:
    """Handles the actual rendering API calls and binary file downloads."""

    def render(self, task: GenerationTask) -> tuple[str, float]:
        """
        Executes the rendering task.
        In a real implementation, this would make an HTTP request to ComfyUI/RunPod/Replicate,
        wait for the generation, and download the resulting PNG to a temp file.
        
        Returns:
            Tuple containing the absolute path to the generated image temp file, and the generation time.
        """
        start_time = time.time()
        
        # 1. Fetch adapter and format payload
        adapter = ImageAdapterRegistry.get(task.model_name)
        payload = adapter.format_parameters(task.parameters)
        
        # Simulate network latency and GPU rendering
        time.sleep(0.5) 
        
        # Simulate physical file creation
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            
            # Write a tiny valid PNG signature or just dummy bytes for now
            # In a real environment, we write the bytes received from the backend
            with open(temp_path, "wb") as f:
                # Minimal valid PNG header for structural testing
                f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
                
            duration = time.time() - start_time
            return temp_path, duration
            
        except Exception as e:
            raise ImageAdapterError(f"Failed to render image for scene {task.scene_number}: {e}") from e
