from unittest.mock import MagicMock, patch

import pytest

from providers.gemini_provider import GeminiProvider
from providers.provider_exceptions import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
)
from providers.provider_models import ProviderHealthStatus


@pytest.fixture
def gemini_provider():
    config = {
        "api_key": "test_key",
        "default_model": "gemini-1.5-pro-latest",
        "default_embedding_model": "text-embedding-004",
        "timeout_seconds": 1
    }
    provider = GeminiProvider(config=config)
    provider.initialize()
    return provider


def test_initialization_no_key():
    provider = GeminiProvider(config={"api_key": ""})
    with pytest.raises(ProviderConfigurationError):
        provider.initialize()


@patch("requests.post")
def test_generate_success(mock_post, gemini_provider):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Hello Gemini"}]
                }
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 20,
            "candidatesTokenCount": 10,
            "totalTokenCount": 30
        }
    }
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    response = gemini_provider.generate("System", "User")
    assert response.text == "Hello Gemini"
    assert response.provider_id == "gemini"
    assert response.token_usage.input_tokens == 20
    assert response.token_usage.output_tokens == 10
    assert response.token_usage.total_tokens == 30
    assert response.cost > 0.0


@patch("requests.post")
def test_generate_auth_error(mock_post, gemini_provider):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_post.return_value = mock_response
    
    with pytest.raises(ProviderAuthenticationError):
        gemini_provider.generate("System", "User")


@patch("requests.post")
def test_embed_success(mock_post, gemini_provider):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "embedding": {
            "values": [0.5, 0.6]
        }
    }
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    response = gemini_provider.embed("Test text")
    assert response.dimensions == 2
    assert response.vector == [0.5, 0.6]


@patch("requests.get")
def test_health_check_healthy(mock_get, gemini_provider):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    assert gemini_provider.health_check() == ProviderHealthStatus.HEALTHY


@patch("requests.get")
def test_health_check_unauthorized(mock_get, gemini_provider):
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_get.return_value = mock_response
    assert gemini_provider.health_check() == ProviderHealthStatus.UNAVAILABLE
