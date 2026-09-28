"""
Tests for Production ComfyUI Integration.
"""
import pytest
from unittest.mock import Mock, patch

from core.integrations.comfyui.client import ComfyUIClient
from core.integrations.comfyui.exceptions import ComfyUIServerOfflineError, WorkflowExecutionError
from core.integrations.comfyui.models import ComfyUIWorkflow

class TestComfyUIClient:
    
    @patch("core.integrations.comfyui.client.urllib.request.urlopen")
    def test_health_check_offline(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        
        client = ComfyUIClient()
        with pytest.raises(ComfyUIServerOfflineError):
            client._request("/object_info")
            
    @patch("core.integrations.comfyui.client.urllib.request.urlopen")
    def test_queue_prompt_success(self, mock_urlopen):
        import json
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({"prompt_id": "12345", "number": 1}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        client = ComfyUIClient()
        workflow = ComfyUIWorkflow(nodes={"1": {"class_type": "KSampler"}})
        
        response = client.queue_prompt(workflow)
        assert response.prompt_id == "12345"
        assert response.number == 1
        
    @patch("core.integrations.comfyui.client.urllib.request.urlopen")
    def test_get_history(self, mock_urlopen):
        import json
        mock_response = Mock()
        mock_data = {
            "12345": {
                "outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
                "status": {"status_str": "success"}
            }
        }
        mock_response.read.return_value = json.dumps(mock_data).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        client = ComfyUIClient()
        history = client.get_history("12345")
        
        assert history.prompt_id == "12345"
        assert "9" in history.outputs
