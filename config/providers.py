"""
Configuration settings for AI providers.
"""

from typing import Any

# Provider configurations
PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "ollama": {
        "base_url": "http://localhost:11434",
        "default_model": "qwen3:8b",
        "default_embedding_model": "nomic-embed-text",
        "timeout_seconds": 30,
        "models": {
            "general": "qwen3:8b",
            "reasoning": "deepseek-r1:8b",
            "coding": "qwen2.5-coder:7b",
            "vision": "qwen2.5vl:7b",
            "fast": "gemma4:e4b",
        },
    },
    "gemini": {
        "api_key": "",  # To be loaded from environment or secret manager
        "default_model": "gemini-1.5-pro-latest",
        "default_embedding_model": "text-embedding-004",
        "timeout_seconds": 30,
    },
    "minimax": {
        "api_key": "",
        "base_url": "https://api.minimax.io",
        "default_model": "MiniMax-M2.7",
        "timeout_seconds": 30,
    },
}
