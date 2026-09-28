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
_DEFAULT_KNOWLEDGE_DB = str(
    Path.home() / ".jarvis" / "knowledge.db"
)


@dataclass(frozen=True)
class JarvisConfig:
    """Immutable configuration for the Jarvis agent framework."""

    provider: str = "ollama"
    model: str = "qwen3:8b"
    ollama_host: str = "http://localhost:11434"
    max_retries: int = 3
    request_timeout: int = 30
    retry_backoff_seconds: float = 1.0
    memory_db_path: str = _DEFAULT_MEMORY_DB
    
    # Specialized Model Roles
    model_general: str = "qwen3:8b"
    model_reasoning: str = "deepseek-r1:8b"
    model_coding: str = "qwen2.5-coder:7b"
    model_vision: str = "qwen2.5vl:7b"
    model_fast: str = "gemma4:e4b"

    # Knowledge / PKI
    embedding_model: str = "nomic-embed-text"
    knowledge_db_path: str = _DEFAULT_KNOWLEDGE_DB
    knowledge_scan_interval_seconds: int = 300

    # n8n Integration
    n8n_host: str = "http://localhost:5678"
    n8n_api_key: str = ""

    def get_role_models(self) -> dict[str, str]:
        """Return dictionary mapping semantic roles to model tags."""
        return {
            "general": self.model_general or self.model,
            "reasoning": self.model_reasoning,
            "coding": self.model_coding,
            "vision": self.model_vision,
            "fast": self.model_fast,
        }


def load_config() -> JarvisConfig:
    """Load configuration from environment variables with defaults.

    Environment variables:
        JARVIS_PROVIDER: AI provider name (default: ollama)
        JARVIS_MODEL: Model name (default: qwen3:8b)
        JARVIS_MODEL_GENERAL: General role model (default: qwen3:8b)
        JARVIS_MODEL_REASONING: Reasoning role model (default: deepseek-r1:8b)
        JARVIS_MODEL_CODING: Coding role model (default: qwen2.5-coder:7b)
        JARVIS_MODEL_VISION: Vision role model (default: qwen2.5vl:7b)
        JARVIS_MODEL_FAST: Fast role model (default: gemma4:e4b)
        OLLAMA_HOST: Ollama server URL (default: http://localhost:11434)
        JARVIS_MAX_RETRIES: Max LLM retry attempts (default: 3)
        JARVIS_TIMEOUT: Request timeout in seconds (default: 30)
        JARVIS_MEMORY_DB: Path to memory database (default: ~/.jarvis/memory.db)

    Returns:
        JarvisConfig: Frozen configuration instance.
    """
    model = os.environ.get("JARVIS_MODEL", "qwen3:8b")
    return JarvisConfig(
        provider=os.environ.get("JARVIS_PROVIDER", "ollama"),
        model=model,
        model_general=os.environ.get("JARVIS_MODEL_GENERAL", model),
        model_reasoning=os.environ.get("JARVIS_MODEL_REASONING", "deepseek-r1:8b"),
        model_coding=os.environ.get("JARVIS_MODEL_CODING", "qwen2.5-coder:7b"),
        model_vision=os.environ.get("JARVIS_MODEL_VISION", "qwen2.5vl:7b"),
        model_fast=os.environ.get("JARVIS_MODEL_FAST", "gemma4:e4b"),
        ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        max_retries=int(os.environ.get("JARVIS_MAX_RETRIES", "3")),
        request_timeout=int(os.environ.get("JARVIS_TIMEOUT", "30")),
        retry_backoff_seconds=float(
            os.environ.get("JARVIS_RETRY_BACKOFF_SECONDS", "1.0")
        ),
        memory_db_path=os.environ.get("JARVIS_MEMORY_DB", _DEFAULT_MEMORY_DB),
        embedding_model=os.environ.get("JARVIS_EMBEDDING_MODEL", "nomic-embed-text"),
        knowledge_db_path=os.environ.get("JARVIS_KNOWLEDGE_DB", _DEFAULT_KNOWLEDGE_DB),
        knowledge_scan_interval_seconds=int(os.environ.get("JARVIS_KNOWLEDGE_SCAN_INTERVAL", "300")),
        n8n_host=os.environ.get("N8N_HOST", "http://localhost:5678"),
        n8n_api_key=os.environ.get("N8N_API_KEY", ""),
    )
