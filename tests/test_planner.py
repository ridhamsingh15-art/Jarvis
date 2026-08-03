import unittest
from unittest.mock import MagicMock

from core.model_gateway import ModelGateway
from core.planner import Planner
from core.registry import Registry
from providers.provider_models import (
    ModelResponse,
    NoCapableProviderError,
    ProviderExecutionError,
    RouterError,
)


class TestPlanner(unittest.TestCase):
    def setUp(self):
        self.mock_gateway = MagicMock(spec=ModelGateway)
        self.mock_registry = MagicMock(spec=Registry)
        self.mock_registry.describe.return_value = "Mock tools"
        self.planner = Planner(gateway=self.mock_gateway, registry=self.mock_registry)
        
    def test_successful_generation(self):
        """Test that Planner uses the mocked Gateway and correctly parses a successful response."""
        mock_response = ModelResponse(
            text='[{"tool": "browser", "action": "open", "args": {"url": "https://example.com"}}]',
            provider_id="mock_provider",
            model_id="mock_model",
            latency_ms=100
        )
        self.mock_gateway.generate.return_value = mock_response
        
        tasks = self.planner.plan("open example.com")
        
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].tool, "browser")
        self.assertEqual(tasks[0].action, "open_url")
        self.assertEqual(tasks[0].args, {"url": "https://example.com"})
        
        self.mock_gateway.generate.assert_called_once()
        # Planner never creates providers directly
        
    def test_gateway_failure(self):
        """Test Planner handles Gateway failure (RouterError)."""
        self.mock_gateway.generate.side_effect = RouterError("Gateway failed")
        
        with self.assertRaises(RouterError):
            self.planner.plan("open example.com")
            
    def test_provider_unavailable(self):
        """Test Planner handles Provider unavailable (NoCapableProviderError)."""
        self.mock_gateway.generate.side_effect = NoCapableProviderError("No provider available")
        
        with self.assertRaises(RouterError):
            self.planner.plan("open example.com")
            
    def test_provider_execution_error(self):
        """Test Planner handles ProviderExecutionError from Gateway."""
        self.mock_gateway.generate.side_effect = ProviderExecutionError("Provider failed to execute")
        
        with self.assertRaises(RouterError):
            self.planner.plan("open example.com")
            
if __name__ == "__main__":
    unittest.main()
