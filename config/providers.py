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
        "num_ctx": 4096,
        "keep_alive": "5m",
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
        "default_model": "gemini-3.8-flash",
        "default_embedding_model": "gemini-embedding-2",
        "timeout_seconds": 30,
        "models": {
            "general": "gemini-3.8-flash",
            "reasoning": "gemini-4-argon",
            "coding": "gemini-4-argon",
            "vision": "gemini-3.8-flash",
            "fast": "gemini-3.5-flash-lite",
        },
    },
    "minimax": {
        "api_key": "",
        "base_url": "https://api.minimax.io",
        "default_model": "MiniMax-M2.7",
        "timeout_seconds": 30,
        "models": {
            "general": "MiniMax-M2.7",
            "reasoning": "MiniMax-M2.7",
            "coding": "MiniMax-M2.7",
            "vision": "MiniMax-M2.7",
            "fast": "MiniMax-M2.7-highspeed",
        },
    },
}
