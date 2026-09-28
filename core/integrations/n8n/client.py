"""
REST Client for interacting with the n8n API.
"""

import logging
from typing import Any

import requests
from requests.exceptions import RequestException

from config.config import JarvisConfig

from .exceptions import N8nConnectionError, N8nExecutionError

logger = logging.getLogger(__name__)


class N8nClient:
    """A client for the n8n REST API (Workflow Execution and Status)."""

    def __init__(self, config: JarvisConfig) -> None:
        self.host = config.n8n_host.rstrip('/')
        self.api_key = config.n8n_api_key
        self.timeout = 10.0

    @property
    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-N8N-API-KEY"] = self.api_key
        return headers

    def execute_workflow(self, workflow_id: str, payload: dict[str, Any]) -> str:
        """Executes a workflow via the n8n REST API and returns the execution ID.
        
        Note: The n8n API endpoint for execution is POST /api/v1/workflows/{id}/execute.
        """
        url = f"{self.host}/api/v1/workflows/{workflow_id}/execute"
        try:
            logger.debug("Executing n8n workflow %s", workflow_id)
            response = requests.post(url, json=payload, headers=self._headers, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            execution_id = data.get("id")
            if not execution_id:
                raise N8nExecutionError(f"No execution ID returned from n8n for workflow {workflow_id}")
                
            return str(execution_id)
        except RequestException as e:
            logger.error("Failed to execute workflow %s: %s", workflow_id, e)
            raise N8nConnectionError(f"Failed to reach n8n API: {e}") from e

    def get_execution_status(self, execution_id: str) -> dict[str, Any]:
        """Polls the status of an execution.
        
        Returns the raw execution dictionary from n8n.
        Expected keys include: id, finished, mode, startedAt, stoppedAt, status.
        """
        url = f"{self.host}/api/v1/executions/{execution_id}"
        try:
            response = requests.get(url, headers=self._headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error("Failed to get execution status for %s: %s", execution_id, e)
            raise N8nConnectionError(f"Failed to fetch execution {execution_id}: {e}") from e

    def stop_execution(self, execution_id: str) -> bool:
        """Stops a running execution."""
        url = f"{self.host}/api/v1/executions/{execution_id}/stop"
        try:
            response = requests.post(url, headers=self._headers, timeout=self.timeout)
            response.raise_for_status()
            return True
        except RequestException as e:
            logger.error("Failed to stop execution %s: %s", execution_id, e)
            return False
