from unittest.mock import MagicMock, patch

import pytest
import requests

from providers.ollama_provider import OllamaProvider
from providers.provider_exceptions import (
    ProviderTimeoutError,
)
from providers.provider_models import ProviderHealthStatus


@pytest.fixture
def ollama_provider():
    config = {
        "base_url": "http://localhost:11434",
        "default_model": "llama3",
        "default_embedding_model": "nomic-embed-text",
        "timeout_seconds": 1
    }
    return OllamaProvider(config=config)


@patch("requests.post")
def test_generate_success(mock_post, ollama_provider):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "model": "llama3",
        "response": "Hello world",
        "prompt_eval_count": 10,
        "eval_count": 5
    }
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    response = ollama_provider.generate("System", "User")
    assert response.text == "Hello world"
    assert response.provider_id == "ollama"
    assert response.token_usage.input_tokens == 10
    assert response.token_usage.output_tokens == 5
    assert response.token_usage.total_tokens == 15


@patch("requests.post")
def test_generate_timeout(mock_post, ollama_provider):
    mock_post.side_effect = requests.exceptions.Timeout("Timeout")
    with pytest.raises(ProviderTimeoutError):
        ollama_provider.generate("System", "User")
    assert mock_post.call_count == 4


@patch("providers.ollama_provider.time.sleep")
@patch("requests.post")
def test_generate_retries_with_exponential_timeout(mock_post, mock_sleep):
    provider = OllamaProvider({
        "timeout_seconds": 5,
        "max_retries": 2,
        "retry_backoff_seconds": 0.25,
    })
    mock_post.side_effect = [
        requests.exceptions.Timeout("slow"),
        requests.exceptions.Timeout("slow"),
        MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"response": "done"}),
        ),
    ]

    assert provider.generate("System", "User").text == "done"
    assert [call.kwargs["timeout"] for call in mock_post.call_args_list] == [5.0, 10.0, 20.0]
    assert [call.args[0] for call in mock_sleep.call_args_list] == [0.25, 0.5]


@patch("requests.post")
def test_embed_success(mock_post, ollama_provider):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "embedding": [0.1, 0.2, 0.3]
    }
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    response = ollama_provider.embed("Test")
    assert response.dimensions == 3
    assert response.vector == [0.1, 0.2, 0.3]


@patch("requests.get")
def test_health_check_healthy(mock_get, ollama_provider):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    assert ollama_provider.health_check() == ProviderHealthStatus.HEALTHY


@patch("requests.get")
def test_health_check_unavailable(mock_get, ollama_provider):
    mock_get.side_effect = requests.exceptions.ConnectionError("Offline")
    assert ollama_provider.health_check() == ProviderHealthStatus.UNAVAILABLE
