import pytest

from providers.gemini_provider import GeminiProvider
from providers.minimax_provider import MiniMaxProvider
from providers.ollama_provider import OllamaProvider
from providers.provider_exceptions import ProviderConfigurationError
from providers.provider_factory import ProviderFactory


def test_create_ollama_provider():
    provider = ProviderFactory.create_provider("ollama")
    assert isinstance(provider, OllamaProvider)
    assert provider.provider_id == "ollama"


def test_create_gemini_provider():
    provider = ProviderFactory.create_provider("gemini", config={"api_key": "test"})
    assert isinstance(provider, GeminiProvider)
    assert provider.provider_id == "gemini"


def test_create_minimax_provider():
    provider = ProviderFactory.create_provider("minimax", config={"api_key": "test"})
    assert isinstance(provider, MiniMaxProvider)
    assert provider.provider_id == "minimax"


def test_create_unknown_provider():
    with pytest.raises(ProviderConfigurationError):
        ProviderFactory.create_provider("unknown_provider")


def test_register_new_provider():
    class DummyProvider(OllamaProvider):
        @property
        def provider_id(self):
            return "dummy"

    ProviderFactory.register_provider("dummy", DummyProvider)
    provider = ProviderFactory.create_provider("dummy")
    assert isinstance(provider, DummyProvider)
