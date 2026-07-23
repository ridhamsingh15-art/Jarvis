"""
Configuration management for Jarvis.

Loads settings from environment variables with sensible defaults.
All configuration lives in a single immutable dataclass.
"""

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_MEMORY_DB = str(
    Path.home() / ".jarvis" / "memory.db"
)


@dataclass(frozen=True)
class JarvisConfig:
    """Immutable configuration for the Jarvis agent framework."""

    model: str = "qwen3:8b"
    ollama_host: str = "http://localhost:11434"
    max_retries: int = 3
    request_timeout: int = 30
    memory_db_path: str = _DEFAULT_MEMORY_DB


def load_config() -> JarvisConfig:
    """Load configuration from environment variables with defaults.

    Environment variables:
        JARVIS_MODEL: Ollama model name (default: qwen3:8b)
        OLLAMA_HOST: Ollama server URL (default: http://localhost:11434)
        JARVIS_MAX_RETRIES: Max LLM retry attempts (default: 3)
        JARVIS_TIMEOUT: Request timeout in seconds (default: 30)
        JARVIS_MEMORY_DB: Path to memory database (default: ~/.jarvis/memory.db)

    Returns:
        JarvisConfig: Frozen configuration instance.
    """
    return JarvisConfig(
        model=os.environ.get("JARVIS_MODEL", "qwen3:8b"),
        ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        max_retries=int(os.environ.get("JARVIS_MAX_RETRIES", "3")),
        request_timeout=int(os.environ.get("JARVIS_TIMEOUT", "30")),
        memory_db_path=os.environ.get("JARVIS_MEMORY_DB", _DEFAULT_MEMORY_DB),
    )

