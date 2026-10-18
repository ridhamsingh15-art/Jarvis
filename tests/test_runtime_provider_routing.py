"""Acceptance tests for provider-native defaults and live runtime routing."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from config.config import JarvisConfig, load_config
from config.model_config import ModelRouterConfig
from core.exceptions import LLMConnectionError
from core.llm import LLMClient
from core.model_router import ModelRouter
from providers.capabilities import Capability
from providers.fallback_manager import FallbackManager
from providers.health_monitor import HealthMonitor
from providers.provider_exceptions import ProviderConfigurationError
from providers.provider_models import (
    AllProvidersExhaustedError,
    EmbeddingResponse,
    InferenceRequirements,
    ModelResponse,
    NoCapableProviderError,
)
from providers.provider_registry import ProviderRegistry
from providers.runtime_setup import build_provider_registry
from providers.selection_policy import WeightedScorePolicy
from tests.mock_provider import MockProvider


@pytest.fixture(autouse=True)
def clear_provider_environment(monkeypatch):
    for name in (
        "JARVIS_PROVIDER",
        "JARVIS_MODEL",
        "JARVIS_MODEL_GENERAL",
        "JARVIS_MODEL_REASONING",
        "JARVIS_MODEL_CODING",
        "JARVIS_MODEL_VISION",
        "JARVIS_MODEL_FAST",
        "JARVIS_PROVIDER_REASONING",
        "JARVIS_PROVIDER_CODING",
        "JARVIS_PROVIDER_VISION",
        "JARVIS_PROVIDER_FAST",
        "JARVIS_FALLBACK_PROVIDERS",
        "JARVIS_GEMINI_MODEL",
        "JARVIS_GEMINI_MODEL_REASONING",
        "JARVIS_GEMINI_MODEL_CODING",
        "JARVIS_GEMINI_MODEL_VISION",
        "JARVIS_GEMINI_MODEL_FAST",
        "JARVIS_GEMINI_EMBEDDING_MODEL",
        "JARVIS_MINIMAX_MODEL",
        "JARVIS_MINIMAX_MODEL_REASONING",
        "JARVIS_MINIMAX_MODEL_CODING",
        "JARVIS_MINIMAX_MODEL_VISION",
        "JARVIS_MINIMAX_MODEL_FAST",
        "GEMINI_API_KEY",
        "MINIMAX_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_cloud_provider_gets_its_own_default_model(monkeypatch):
    monkeypatch.setenv("JARVIS_PROVIDER", "gemini")
    config = load_config()
    assert config.provider == "gemini"
    assert config.model == "gemini-3.8-flash"
    assert config.model != "qwen3:8b"
    assert config.fallback_providers == ()


def test_explicit_model_overrides_provider_default(monkeypatch):
    monkeypatch.setenv("JARVIS_PROVIDER", "gemini")
    monkeypatch.setenv("JARVIS_MODEL", "gemini-custom-model")
    config = load_config()
    assert config.model == "gemini-custom-model"


def test_fallback_provider_list_is_normalized_and_ordered(monkeypatch):
    monkeypatch.setenv("JARVIS_FALLBACK_PROVIDERS", " GEMINI, minimax ")
    assert load_config().fallback_providers == ("gemini", "minimax")


@pytest.mark.parametrize(
    ("primary", "fallbacks", "message"),
    [
        ("not-a-provider", "", "Unknown JARVIS_PROVIDER"),
        ("ollama", "ollama,gemini", "cannot also appear"),
        ("ollama", "gemini,gemini", "duplicate"),
        ("ollama", "gemini,not-a-provider", "Unknown fallback provider"),
    ],
)
def test_invalid_provider_config_fails_fast(monkeypatch, primary, fallbacks, message):
    monkeypatch.setenv("JARVIS_PROVIDER", primary)
    monkeypatch.setenv("JARVIS_FALLBACK_PROVIDERS", fallbacks)
    with pytest.raises(ValueError, match=message):
        load_config()


def test_role_provider_override_must_be_enabled_explicitly(monkeypatch):
    monkeypatch.setenv("JARVIS_PROVIDER", "ollama")
    monkeypatch.setenv("JARVIS_PROVIDER_REASONING", "gemini")
    with pytest.raises(ValueError, match="not the primary or an explicitly configured fallback"):
        load_config()


def test_role_provider_override_is_allowed_when_fallback_is_explicit(monkeypatch):
    monkeypatch.setenv("JARVIS_PROVIDER", "ollama")
    monkeypatch.setenv("JARVIS_PROVIDER_REASONING", "gemini")
    monkeypatch.setenv("JARVIS_FALLBACK_PROVIDERS", "gemini")
    config = load_config()
    assert config.reasoning_provider == "gemini"
    assert config.fallback_providers == ("gemini",)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("max_latency_ms", -1, "max_latency_ms"),
        ("max_latency_ms", True, "max_latency_ms"),
        ("max_cost_per_request", -0.1, "max_cost_per_request"),
        ("max_output_tokens", 0, "max_output_tokens"),
        ("max_output_tokens", True, "max_output_tokens"),
        ("min_context_length", 0, "min_context_length"),
    ],
)
def test_invalid_inference_limits_are_rejected(field, value, message):
    with pytest.raises(ValueError, match=message):
        InferenceRequirements(**{field: value})


def test_legacy_positional_jarvis_config_arguments_are_preserved():
    config = JarvisConfig("ollama", "qwen3:8b", "http://localhost:1234")
    assert config.ollama_host == "http://localhost:1234"


def test_legacy_positional_router_config_arguments_are_preserved():
    config = ModelRouterConfig(None, None, False)
    assert config.prefer_local is False
    assert config.default_coding_provider is None


def test_runtime_registry_defaults_to_only_primary_provider(monkeypatch):
    config = load_config()
    registry, _ = build_provider_registry(config)
    assert [p.provider_id for p in registry.list_providers()] == ["ollama"]


def test_runtime_registry_registers_only_explicitly_enabled_fallbacks(monkeypatch):
    monkeypatch.setenv("JARVIS_FALLBACK_PROVIDERS", "gemini,minimax")
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-gemini-key")
    monkeypatch.setenv("MINIMAX_API_KEY", "unit-test-minimax-key")
    config = load_config()
    registry, _ = build_provider_registry(config)
    assert [p.provider_id for p in registry.list_providers()] == [
        "ollama", "gemini", "minimax"
    ]


def test_missing_optional_fallback_credentials_do_not_break_primary(monkeypatch):
    monkeypatch.setenv("JARVIS_FALLBACK_PROVIDERS", "gemini,minimax")
    config = load_config()
    registry, _ = build_provider_registry(config)
    assert [p.provider_id for p in registry.list_providers()] == ["ollama"]


def test_cloud_primary_uses_native_model_and_roles_without_ollama_tag(monkeypatch):
    monkeypatch.setenv("JARVIS_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-gemini-key")
    config = load_config()
    registry, _ = build_provider_registry(config)
    provider = registry.get_provider("gemini")
    assert provider is not None
    assert provider._default_model == "gemini-3.8-flash"
    assert provider._models["general"] == "gemini-3.8-flash"
    assert provider._models["reasoning"] == "gemini-4-argon"
    assert provider._default_embed_model == "gemini-embedding-2"


def test_ollama_primary_keeps_role_map_and_runtime_options(monkeypatch):
    monkeypatch.setenv("JARVIS_MODEL", "qwen-custom:latest")
    monkeypatch.setenv("JARVIS_NUM_CTX", "8192")
    monkeypatch.setenv("JARVIS_KEEP_ALIVE", "10m")
    config = load_config()
    registry, _ = build_provider_registry(config)
    provider = registry.get_provider("ollama")
    assert provider is not None
    assert provider._default_model == "qwen-custom:latest"
    assert provider._models["general"] == "qwen-custom:latest"
    assert provider._num_ctx == 8192
    assert provider._keep_alive == "10m"


def test_runtime_registry_fails_fast_for_primary_without_credentials(monkeypatch):
    monkeypatch.setenv("JARVIS_PROVIDER", "gemini")
    config = load_config()
    with pytest.raises(ProviderConfigurationError, match="API key"):
        build_provider_registry(config)


def _make_router(config: ModelRouterConfig, providers: list[MockProvider]) -> ModelRouter:
    health = HealthMonitor()
    registry = ProviderRegistry(health)
    for provider in providers:
        registry.register(provider)
    return ModelRouter(
        config=config,
        registry=registry,
        selection_policy=WeightedScorePolicy(health),
        fallback_manager=FallbackManager(max_fallback_attempts=2),
        health_monitor=health,
    )


def test_router_uses_configured_chat_provider_as_default():
    local = MockProvider("local", "Local", [Capability.CHAT], is_local=True)
    remote = MockProvider("remote", "Remote", [Capability.CHAT], is_local=False)
    router = _make_router(
        ModelRouterConfig(default_chat_provider="remote", prefer_local=True),
        [local, remote],
    )
    merged = router._merge_requirements(None, Capability.CHAT)
    assert merged.prefer_provider == "remote"
    response = router.generate("system", "user")
    assert response.provider_id == "remote"


def test_explicit_request_provider_preference_overrides_default():
    local = MockProvider("local", "Local", [Capability.CHAT], is_local=True)
    remote = MockProvider("remote", "Remote", [Capability.CHAT], is_local=False)
    router = _make_router(
        ModelRouterConfig(default_chat_provider="remote", prefer_local=True),
        [local, remote],
    )
    req = InferenceRequirements(
        capabilities=frozenset([Capability.CHAT]),
        prefer_provider="local",
    )
    assert router._merge_requirements(req, Capability.CHAT).prefer_provider == "local"
    assert router.generate("system", "user", req).provider_id == "local"


def test_router_uses_role_provider_preference_without_overriding_explicit_request():
    local = MockProvider("local", "Local", [Capability.CHAT, Capability.REASONING], is_local=True)
    remote = MockProvider("remote", "Remote", [Capability.CHAT, Capability.REASONING], is_local=False)
    router = _make_router(
        ModelRouterConfig(
            default_chat_provider="local",
            default_reasoning_provider="remote",
            prefer_local=True,
        ),
        [local, remote],
    )
    req = InferenceRequirements(
        capabilities=frozenset([Capability.REASONING]),
        role="reasoning",
    )
    assert router._merge_requirements(req, Capability.CHAT).prefer_provider == "remote"
    explicit = InferenceRequirements(
        capabilities=frozenset([Capability.REASONING]),
        role="reasoning",
        prefer_provider="local",
    )
    assert router._merge_requirements(explicit, Capability.CHAT).prefer_provider == "local"


def test_llm_client_routes_generation_and_embeddings_through_gateway():
    config = JarvisConfig()
    gateway = MagicMock()
    gateway.generate.return_value = ModelResponse(
        text="gateway response", provider_id="gemini", model_id="gemini-3.8-flash", latency_ms=3
    )
    gateway.embed.return_value = EmbeddingResponse(
        vector=[0.1, 0.2], dimensions=2, provider_id="ollama", model_id="nomic-embed-text", latency_ms=1
    )
    client = LLMClient(config, gateway=gateway)
    with patch("core.llm.chat") as direct_chat, patch("core.llm.embeddings") as direct_embeddings:
        assert client.generate("sys", "prompt") == "gateway response"
        assert client.get_embeddings("embedding input") == [0.1, 0.2]
        direct_chat.assert_not_called()
        direct_embeddings.assert_not_called()
    assert gateway.generate.call_count == 1
    assert gateway.generate.call_args.kwargs["requirements"].role == "general"
    assert Capability.EMBEDDINGS in gateway.embed.call_args.kwargs["requirements"].capabilities


def test_llm_client_passes_explicit_coding_and_reasoning_roles_to_gateway():
    gateway = MagicMock()
    gateway.generate.side_effect = [
        ModelResponse(text="code", provider_id="gemini", model_id="gemini-4-argon", latency_ms=4),
        ModelResponse(text="reasoned", provider_id="gemini", model_id="gemini-4-argon", latency_ms=5),
    ]
    client = LLMClient(JarvisConfig(), gateway=gateway)
    coding = InferenceRequirements(
        capabilities=frozenset([Capability.CODING]),
        role="coding",
        prefer_model="gemini-4-argon",
    )
    reasoning = InferenceRequirements(
        capabilities=frozenset([Capability.REASONING]),
        role="reasoning",
        task_complexity="COMPLEX",
    )
    assert client.generate("system", "write code", requirements=coding) == "code"
    assert client.generate("system", "reason through", requirements=reasoning) == "reasoned"
    assert gateway.generate.call_args_list[0].kwargs["requirements"] is coding
    assert gateway.generate.call_args_list[1].kwargs["requirements"] is reasoning


def test_llm_client_passes_explicit_embedding_requirements_to_gateway():
    gateway = MagicMock()
    gateway.embed.return_value = EmbeddingResponse(
        vector=[0.4], dimensions=1, provider_id="gemini", model_id="gemini-embedding-2", latency_ms=2
    )
    client = LLMClient(JarvisConfig(), gateway=gateway)
    requirements = InferenceRequirements(
        capabilities=frozenset([Capability.EMBEDDINGS]),
        prefer_provider="gemini",
    )
    assert client.get_embeddings("input", requirements=requirements) == [0.4]
    assert gateway.embed.call_args.kwargs["requirements"] is requirements


def test_llm_client_translates_router_errors_without_leaking_provider_details():
    gateway = MagicMock()
    gateway.generate.side_effect = AllProvidersExhaustedError("secret-bearing-provider-error")
    client = LLMClient(JarvisConfig(), gateway=gateway)
    with pytest.raises(LLMConnectionError, match="AllProvidersExhaustedError") as caught:
        client.generate("sys", "prompt")
    assert "secret-bearing-provider-error" not in str(caught.value)


def test_llm_client_builds_shared_gateway_by_default(monkeypatch):
    from providers import runtime_setup

    sentinel = object()
    with patch.object(runtime_setup, "build_model_gateway", return_value=sentinel) as build:
        client = LLMClient(JarvisConfig())
    build.assert_called_once()
    assert client._gateway is sentinel


def test_direct_ollama_mode_is_explicit_and_rejects_cloud_config():
    client = LLMClient(JarvisConfig(), direct_ollama=True)
    assert client._gateway is None
    with pytest.raises(ValueError, match="requires JARVIS_PROVIDER=ollama"):
        LLMClient(JarvisConfig(provider="gemini", model="gemini-3.8-flash"), direct_ollama=True)


def test_embedding_cost_ceiling_routes_to_provider_with_known_acceptable_cost():
    class EmbeddingPricedProvider(MockProvider):
        def __init__(self, provider_id, is_local, estimated_cost):
            super().__init__(provider_id, provider_id, [Capability.EMBEDDINGS], is_local=is_local)
            self.estimated_cost = estimated_cost

        def estimate_embedding_cost(self, input_tokens, model_id=None):
            return self.estimated_cost

    expensive = EmbeddingPricedProvider("expensive", False, 0.05)
    local = EmbeddingPricedProvider("local", True, 0.0)
    router = _make_router(
        ModelRouterConfig(default_chat_provider="expensive", prefer_local=False),
        [expensive, local],
    )
    req = InferenceRequirements(
        capabilities=frozenset([Capability.EMBEDDINGS]),
        max_cost_per_request=0.01,
    )
    response = router.embed("embedding text", req)
    assert response.provider_id == "local"


def test_context_limit_excludes_known_small_cloud_model():
    class ContextProvider(MockProvider):
        def __init__(self, provider_id, context):
            super().__init__(provider_id, provider_id, [Capability.CHAT], is_local=False)
            self.context = context

        def context_window_tokens(self, requirements=None):
            return self.context

    small = ContextProvider("small", 4096)
    large = ContextProvider("large", 1_000_000)
    router = _make_router(
        ModelRouterConfig(default_chat_provider="small", prefer_local=False),
        [small, large],
    )
    req = InferenceRequirements(
        capabilities=frozenset([Capability.CHAT]),
        prefer_provider="small",
        min_context_length=8000,
    )
    response = router.generate("system", "question", req)
    assert response.provider_id == "large"


def test_unknown_context_size_is_not_misrepresented_as_verified():
    from providers.gemini_provider import GeminiProvider
    from providers.minimax_provider import MiniMaxProvider

    gemini = GeminiProvider({"api_key": "test", "default_model": "custom-gemini-model"})
    minimax = MiniMaxProvider({"api_key": "test", "default_model": "custom-minimax-model"})
    assert gemini.context_window_tokens() is None
    assert minimax.context_window_tokens() is None


def test_text_only_api_adapters_do_not_advertise_image_transport():
    from providers.gemini_provider import GeminiProvider
    from providers.ollama_provider import OllamaProvider

    assert Capability.VISION not in GeminiProvider({"api_key": "test"}).capabilities
    assert Capability.VISION not in OllamaProvider().capabilities


def test_cost_estimator_exception_excludes_cloud_provider():
    class BrokenEstimator(MockProvider):
        def estimate_cost(self, input_tokens, output_tokens, model_id=None):
            raise RuntimeError("sensitive internal detail")

    broken = BrokenEstimator("broken", "Broken", [Capability.CHAT], is_local=False)
    local = MockProvider("local", "Local", [Capability.CHAT], is_local=True)
    router = _make_router(
        ModelRouterConfig(default_chat_provider="broken", prefer_local=False),
        [broken, local],
    )
    req = InferenceRequirements(
        capabilities=frozenset([Capability.CHAT]),
        max_cost_per_request=0.01,
        max_output_tokens=128,
    )
    assert router.generate("system", "question", req).provider_id == "local"


def test_cost_ceiling_without_output_bound_does_not_send_request_to_cloud():
    class PricedProvider(MockProvider):
        def estimate_cost(self, input_tokens, output_tokens, model_id=None):
            return 0.01

    local = MockProvider("local", "Local", [Capability.CHAT], is_local=True)
    cloud = PricedProvider("cloud", "Cloud", [Capability.CHAT], is_local=False)
    router = _make_router(
        ModelRouterConfig(default_chat_provider="cloud", prefer_local=False),
        [cloud, local],
    )
    req = InferenceRequirements(
        capabilities=frozenset([Capability.CHAT]),
        prefer_provider="cloud",
        max_cost_per_request=0.005,
    )
    response = router.generate("system", "question", req)
    assert response.provider_id == "local"


def test_cost_ceiling_filters_cloud_by_published_estimate_with_output_cap():
    class PricedProvider(MockProvider):
        def __init__(self, provider_id, estimated_cost):
            super().__init__(provider_id, provider_id, [Capability.CHAT], is_local=False)
            self.estimated_cost = estimated_cost

        def estimate_cost(self, input_tokens, output_tokens, model_id=None):
            return self.estimated_cost

    affordable = PricedProvider("affordable", 0.001)
    expensive = PricedProvider("expensive", 0.02)
    router = _make_router(
        ModelRouterConfig(default_chat_provider="expensive", prefer_local=False),
        [expensive, affordable],
    )
    req = InferenceRequirements(
        capabilities=frozenset([Capability.CHAT]),
        prefer_provider="expensive",
        max_cost_per_request=0.01,
        max_output_tokens=1024,
    )
    response = router.generate("system", "question", req)
    assert response.provider_id == "affordable"


def test_cost_ceiling_with_unknown_cloud_pricing_fails_closed():
    class UnknownCostProvider(MockProvider):
        def estimate_cost(self, input_tokens, output_tokens, model_id=None):
            return None

    unknown = UnknownCostProvider("unknown", "Unknown", [Capability.CHAT], is_local=False)
    router = _make_router(
        ModelRouterConfig(default_chat_provider="unknown", prefer_local=False),
        [unknown],
    )
    req = InferenceRequirements(
        capabilities=frozenset([Capability.CHAT]),
        max_cost_per_request=0.01,
        max_output_tokens=128,
    )
    with pytest.raises(NoCapableProviderError, match="latency/cost constraints"):
        router.generate("system", "question", req)


def test_router_learns_latency_and_excludes_known_over_budget_provider():
    slow = MockProvider("slow", "Slow", [Capability.CHAT], is_local=False)
    fast = MockProvider("fast", "Fast", [Capability.CHAT], is_local=False)
    router = _make_router(
        ModelRouterConfig(default_chat_provider="slow", prefer_local=False),
        [slow, fast],
    )
    router._health_monitor.record_latency("slow", 500)
    req = InferenceRequirements(
        capabilities=frozenset([Capability.CHAT]),
        prefer_provider="slow",
        max_latency_ms=100,
    )
    response = router.generate("system", "question", req)
    assert response.provider_id == "fast"


def test_estimated_cost_uses_current_model_rates_and_unknown_is_not_free():
    from providers.gemini_provider import GeminiProvider
    from providers.minimax_provider import MiniMaxProvider

    gemini = GeminiProvider({"api_key": "test", "default_model": "gemini-3.8-flash"})
    assert gemini.estimate_cost(1_000_000, 1_000_000) == pytest.approx(9.0)
    assert gemini.estimate_cost(1_000_000, 1_000_000, "gemini-4-argon") == pytest.approx(24.0)
    assert gemini.estimate_cost(1_000, 1_000, "unknown-model") is None
    minimax = MiniMaxProvider({"api_key": "test", "default_model": "MiniMax-M2.7"})
    assert minimax.estimate_cost(1_000_000, 1_000_000) == pytest.approx(1.5)
    assert minimax.estimate_cost(1_000_000, 1_000_000, "MiniMax-M2.7-highspeed") == pytest.approx(3.0)
    assert minimax.estimate_cost(1_000, 1_000, "unknown-model") is None


def test_gemini_and_minimax_model_resolution_honors_role_and_explicit_model():
    from providers.gemini_provider import GeminiProvider
    from providers.minimax_provider import MiniMaxProvider

    gemini = GeminiProvider({
        "api_key": "test",
        "default_model": "gemini-general",
        "models": {"general": "gemini-general", "reasoning": "gemini-reasoning"},
    })
    minimax = MiniMaxProvider({
        "api_key": "test",
        "default_model": "minimax-general",
        "models": {"general": "minimax-general", "coding": "minimax-coding"},
    })
    assert gemini._resolve_model(InferenceRequirements(role="reasoning")) == "gemini-reasoning"
    assert gemini._resolve_model(InferenceRequirements(prefer_model="gemini-pinned")) == "gemini-pinned"
    assert minimax._resolve_model(InferenceRequirements(role="coding")) == "minimax-coding"
    assert minimax._resolve_model(InferenceRequirements(prefer_model="minimax-pinned")) == "minimax-pinned"
