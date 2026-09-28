from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import RequestException

from config.config import JarvisConfig
from core.events.bus import EventBus
from core.integrations.n8n.client import N8nClient
from core.integrations.n8n.installer import N8nInstaller
from core.integrations.n8n.models import N8nWorkflow
from core.integrations.n8n.telemetry import N8nTelemetry
from core.integrations.n8n.workflow_registry import N8nWorkflowRegistry
from core.integrations.n8n.workflow_runner import N8nWorkflowRunner
from core.mission.models import Mission


@pytest.fixture
def config():
    return JarvisConfig(n8n_host="http://localhost:5678", n8n_api_key="test_key")


@pytest.fixture
def event_bus():
    return EventBus(logger=MagicMock())


@pytest.fixture
def mission_manager():
    manager = MagicMock()
    # Mock mission creation
    mission = Mission(title="test", description="desc", priority=1)
    # We will use the dynamically generated ID
    manager.create.return_value = mission
    
    # Mock mission retrieval
    manager.get.return_value = mission
    return manager


def test_n8n_installer(config, event_bus):
    installer = N8nInstaller(config, event_bus)
    
    # Test checking health with mock
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        assert installer.check_health() is True
        
        mock_get.side_effect = RequestException()
        assert installer.check_health() is False


def test_n8n_client(config):
    client = N8nClient(config)
    
    with patch("requests.post") as mock_post:
        # Mock successful execution
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"id": "exec-123"}
        
        exec_id = client.execute_workflow("wf-1", {"test": "data"})
        assert exec_id == "exec-123"
        mock_post.assert_called_once()
        
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"finished": True}
        
        status = client.get_execution_status("exec-123")
        assert status["finished"] is True


def test_n8n_workflow_registry():
    registry = N8nWorkflowRegistry()
    wf = N8nWorkflow(id="1", name="UploadYouTube", description="Uploads video")
    
    registry.register(wf)
    retrieved = registry.get("uploadyoutube")
    
    assert retrieved.id == "1"
    assert len(registry.list_all()) == 1


def test_n8n_workflow_runner(config, mission_manager, event_bus):
    client = MagicMock()
    client.execute_workflow.return_value = "exec-123"
    
    # Force it to finish on first poll
    client.get_execution_status.return_value = {"finished": True}
    
    telemetry = N8nTelemetry(event_bus)
    runner = N8nWorkflowRunner(client, mission_manager, telemetry)
    
    wf = N8nWorkflow(id="1", name="Test", description="Test")
    
    # Execute
    mission_id = runner.execute_async(wf, {"test": "data"})
    assert mission_id == mission_manager.create.return_value.mission_id.value
    
    # Reset mocks since execute_async spawns a thread that might have already hit them
    mission_manager.reset_mock()
    
    # Runner operates async. We mock the run_and_monitor synchronously to test logic.
    runner._run_and_monitor(mission_id, wf, {"test": "data"})
    
    # Verify mission states
    mission_manager.ready.assert_called_once_with(mission_id)
    mission_manager.resume.assert_called_once_with(mission_id)
    mission_manager.complete.assert_called_once_with(mission_id)
