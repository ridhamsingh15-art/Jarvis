"""
ComfyUI Downloader.

Fetches the resulting images/videos from the server.
"""
import logging
import urllib.request
import urllib.parse
from typing import List

from .client import ComfyUIClient
from .models import QueueHistory, ImageOutput
from .exceptions import ImageDownloadError

logger = logging.getLogger(__name__)

class ComfyUIDownloader:
    """Downloads outputs from ComfyUI."""

    def __init__(self, client: ComfyUIClient):
        self.client = client

    def get_image_data(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        """Download a single image file."""
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        url = f"{self.client.base_url}/view?{url_values}"
        
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read()
        except Exception as e:
            logger.error(f"Failed to download image {filename}: {e}")
            raise ImageDownloadError(f"Could not download {filename}") from e

    def download_outputs(self, history: QueueHistory) -> List[ImageOutput]:
        """Parse history and download all generated outputs."""
        logger.info(f"Downloading outputs for prompt {history.prompt_id}...")
        outputs = []
        
        for node_id, node_output in history.outputs.items():
            if 'images' in node_output:
                for image in node_output['images']:
                    filename = image.get('filename')
                    subfolder = image.get('subfolder', '')
                    folder_type = image.get('type', 'output')
                    
                    data = self.get_image_data(filename, subfolder, folder_type)
                    outputs.append(ImageOutput(
                        filename=filename,
                        subfolder=subfolder,
                        type=folder_type,
                        data=data
                    ))
                    
            if 'gifs' in node_output: # AnimateDiff
                for gif in node_output['gifs']:
                    filename = gif.get('filename')
                    subfolder = gif.get('subfolder', '')
                    folder_type = gif.get('type', 'output')
                    
                    data = self.get_image_data(filename, subfolder, folder_type)
                    outputs.append(ImageOutput(
                        filename=filename,
                        subfolder=subfolder,
                        type=folder_type,
                        data=data
                    ))
                    
        return outputs
