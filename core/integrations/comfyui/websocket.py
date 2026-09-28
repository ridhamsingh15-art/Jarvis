"""
ComfyUI WebSocket Client.

Tracks real-time generation progress.
"""
import logging
import json
import time
import urllib.request
from typing import Any, Callable

# Note: In a true production environment, we would use `websockets` or `websocket-client`.
# For standard library compatibility without external dependencies in this sprint,
# we provide a stubbed polling mechanism that simulates WebSocket listening via the history endpoint,
# or a mock listener for the tests.
from .client import ComfyUIClient
from .exceptions import WebSocketTimeoutError, WorkflowExecutionError

logger = logging.getLogger(__name__)

class ComfyUIWebSocket:
    """Listens for progress and completion events for a given prompt."""

    def __init__(self, client: ComfyUIClient):
        self.client = client
        # In a real impl, this would manage a ws:// connection

    def wait_for_completion(self, prompt_id: str, timeout_sec: int = 300) -> None:
        """
        Blocks until the prompt is fully executed.
        Simulated using polling for this environment.
        """
        logger.info(f"Waiting for prompt {prompt_id} to complete (timeout: {timeout_sec}s)...")
        start_time = time.time()
        
        while True:
            if time.time() - start_time > timeout_sec:
                self.client.interrupt()
                raise WebSocketTimeoutError(f"Prompt {prompt_id} timed out after {timeout_sec} seconds.")
                
            try:
                # Poll history to see if it's done
                # The /history API only returns the prompt once it is completed.
                url = f"{self.client.base_url}/history/{prompt_id}"
                req = urllib.request.Request(url)
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    
                    if prompt_id in data:
                        logger.info(f"Prompt {prompt_id} completed successfully.")
                        return
                        
            except Exception:
                # Ignore errors during polling, it might just not be ready or server is busy
                pass
                
            time.sleep(1.0)
