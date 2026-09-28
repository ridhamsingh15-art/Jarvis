"""
ComfyUI Uploader.

Handles uploading input images or masks to ComfyUI.
"""
import logging
from .client import ComfyUIClient

logger = logging.getLogger(__name__)

class ComfyUIUploader:
    """Uploads assets to the ComfyUI server."""
    
    def __init__(self, client: ComfyUIClient):
        self.client = client
        
    def upload_image(self, file_path: str) -> str:
        """
        Upload an image to ComfyUI.
        Returns the filename on the server.
        """
        logger.info(f"Uploading image {file_path} to ComfyUI...")
        # Stub: Uses multi-part form upload to /upload/image
        # For this sprint, we assume success.
        return "uploaded_image.png"
