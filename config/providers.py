"""
Configuration settings for AI providers.
"""

from typing import Dict, Any

# Provider configurations
PROVIDER_CONFIG: Dict[str, Dict[str, Any]] = {
    "ollama": {
        "base_url": "http://localhost:11434",
        "default_model": "llama3",
        "default_embedding_model": "nomic-embed-text",
        "timeout_seconds": 30,
    },
    "gemini": {
        "api_key": "", # To be loaded from environment or secret manager
        "default_model": "gemini-1.5-pro-latest",
        "default_embedding_model": "text-embedding-004",
        "timeout_seconds": 30,
    }
}
