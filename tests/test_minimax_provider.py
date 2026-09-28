from unittest.mock import MagicMock, patch

import pytest

from providers.minimax_provider import MiniMaxProvider
from providers.provider_exceptions import ProviderConfigurationError
from providers.provider_models import ProviderHealthStatus


def test_initialization_requires_an_api_key() -> None:
    with pytest.raises(ProviderConfigurationError):
        MiniMaxProvider(config={"api_key": ""}).initialize()


@patch("requests.post")
def test_generate_uses_minimax_chat_endpoint(mock_post: MagicMock) -> None:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "choices": [{"message": {"content": "Hello from MiniMax"}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
    }
    mock_post.return_value = response
    provider = MiniMaxProvider(config={"api_key": "test-key", "timeout_seconds": 1})

    result = provider.generate("system", "hello")

    assert result.text == "Hello from MiniMax"
    assert result.token_usage.total_tokens == 7
    assert mock_post.call_args.args[0].endswith("/v1/text/chatcompletion_v2")


@patch("requests.get")
def test_health_check_is_unavailable_without_a_key(mock_get: MagicMock) -> None:
    assert (
        MiniMaxProvider(config={"api_key": ""}).health_check()
        == ProviderHealthStatus.UNAVAILABLE
    )
    mock_get.assert_not_called()
