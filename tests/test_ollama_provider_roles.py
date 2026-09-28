"""
Tests for OllamaProvider multi-model role routing and fallback.
"""
from unittest.mock import patch, MagicMock
from providers.capabilities import Capability
from providers.ollama_provider import OllamaProvider
from providers.provider_models import InferenceRequirements


def test_ollama_provider_role_resolution():
    config = {
        "default_model": "qwen3:8b",
        "models": {
            "general": "qwen3:8b",
            "coding": "qwen2.5-coder:7b",
            "reasoning": "deepseek-r1:8b",
            "vision": "qwen2.5vl:7b",
            "fast": "gemma4:e4b",
        }
    }
    provider = OllamaProvider(config)

    # 1. Default (no reqs)
    assert provider._resolve_model(None) == "qwen3:8b"

    # 2. Capability: CODING
    req_code = InferenceRequirements(capabilities=frozenset([Capability.CODING]))
    assert provider._resolve_model(req_code) == "qwen2.5-coder:7b"

    # 3. Capability: REASONING
    req_reason = InferenceRequirements(capabilities=frozenset([Capability.REASONING]))
    assert provider._resolve_model(req_reason) == "deepseek-r1:8b"

    # 4. Capability: VISION
    req_vision = InferenceRequirements(capabilities=frozenset([Capability.VISION]))
    assert provider._resolve_model(req_vision) == "qwen2.5vl:7b"

    # 5. Fast/simple complexity
    req_fast = InferenceRequirements(task_complexity="SIMPLE")
    assert provider._resolve_model(req_fast) == "gemma4:e4b"

    # 6. Explicit model override
    req_override = InferenceRequirements(prefer_model="custom:latest")
    assert provider._resolve_model(req_override) == "custom:latest"


def test_ollama_provider_fallback_on_failure():
    config = {
        "default_model": "qwen3:8b",
        "models": {
            "general": "qwen3:8b",
            "coding": "broken-coder:7b",
        }
    }
    provider = OllamaProvider(config)

    calls = []

    def mock_post(url, json=None, timeout=None):
        calls.append(json.get("model"))
        if json.get("model") == "broken-coder:7b":
            raise Exception("Model not found")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": "Fallback response"},
            "prompt_eval_count": 10,
            "eval_count": 10,
        }
        return mock_resp

    with patch("requests.post", side_effect=mock_post):
        req_code = InferenceRequirements(capabilities=frozenset([Capability.CODING]))
        resp = provider.generate("system prompt", "debug this", requirements=req_code)

        assert resp.text == "Fallback response"
        assert resp.model_id == "qwen3:8b"
        # First tried broken-coder:7b, then fell back to qwen3:8b
        assert calls == ["broken-coder:7b", "qwen3:8b"]
