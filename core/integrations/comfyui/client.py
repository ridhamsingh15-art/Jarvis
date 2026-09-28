"""
ComfyUI REST Client.

Handles the standard HTTP API wrapper.
"""
import logging
import urllib.request
import urllib.error
import urllib.parse
import json
import uuid
from typing import Any, Dict

from .models import ComfyUIWorkflow, PromptResponse, QueueHistory
from .exceptions import ComfyUIServerOfflineError, WorkflowExecutionError

logger = logging.getLogger(__name__)

class ComfyUIClient:
    """REST API Client for ComfyUI."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8188):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.client_id = str(uuid.uuid4())

    def _request(self, endpoint: str, method: str = "GET", data: Dict[str, Any] = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        req = urllib.request.Request(url, method=method)
        
        if data is not None:
            json_data = json.dumps(data).encode("utf-8")
            req.add_header("Content-Type", "application/json")
            req.data = json_data

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            logger.error(f"ComfyUI connection error: {e}")
            raise ComfyUIServerOfflineError(f"Failed to connect to {url}") from e
        except Exception as e:
            raise WorkflowExecutionError(f"Error during request to {url}: {e}") from e

    def queue_prompt(self, workflow: ComfyUIWorkflow) -> PromptResponse:
        """Queue a workflow for generation."""
        logger.info("Queueing ComfyUI prompt...")
        payload = {
            "prompt": workflow.nodes,
            "client_id": self.client_id
        }
        
        resp = self._request("/prompt", method="POST", data=payload)
        
        if "error" in resp:
            raise WorkflowExecutionError(f"Error queueing prompt: {resp['error']}")
            
        return PromptResponse(
            prompt_id=resp.get("prompt_id"),
            number=resp.get("number", 0),
            node_errors=resp.get("node_errors", {})
        )

    def get_history(self, prompt_id: str) -> QueueHistory:
        """Fetch the history of a specific prompt."""
        resp = self._request(f"/history/{prompt_id}")
        
        if prompt_id not in resp:
            raise WorkflowExecutionError(f"Prompt {prompt_id} not found in history.")
            
        data = resp[prompt_id]
        return QueueHistory(
            prompt_id=prompt_id,
            outputs=data.get("outputs", {}),
            status=data.get("status", {})
        )

    def interrupt(self) -> None:
        """Cancel the currently running workflow."""
        logger.info("Interrupting current ComfyUI workflow...")
        try:
            self._request("/interrupt", method="POST")
        except Exception as e:
            logger.warning(f"Failed to interrupt workflow: {e}")
