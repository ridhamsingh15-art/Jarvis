"""
ComfyUI Health Checker.

Verifies the server is online.
"""
import logging
from .client import ComfyUIClient
from .exceptions import ComfyUIServerOfflineError

logger = logging.getLogger(__name__)

class ComfyUIHealthCheck:
    """Verifies server health."""

    def __init__(self, client: ComfyUIClient):
        self.client = client

    def check(self) -> bool:
        """Pings the server object_info endpoint to verify it is up."""
        logger.debug("Checking ComfyUI server health...")
        try:
            # /object_info is a lightweight endpoint to verify server is up and returning valid JSON
            self.client._request("/object_info")
            return True
        except Exception as e:
            logger.warning(f"ComfyUI health check failed: {e}")
            raise ComfyUIServerOfflineError("ComfyUI Server is offline or unresponsive.") from e
